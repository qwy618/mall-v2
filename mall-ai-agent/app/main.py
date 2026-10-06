"""AI Agent 服务入口（FastAPI）

启动：.venv\\Scripts\\python -m uvicorn app.main:app --reload --port 8090

接口：
  GET  /health           健康检查
  POST /api/chat         非流式（调试用，session 有记忆）
  POST /api/chat/stream  SSE 流式（H5 聊天页用，session 有记忆）
"""
import json
import logging
import secrets
import sys
import time
from pathlib import Path

# 支持两种运行方式：
# 1) 模块方式（命令行）：python -m app.main 或 uvicorn app.main:app
# 2) 脚本方式（PyCharm 右键 Run 'main'）：__package__ 为 None，相对导入会失败，
#    这里把项目根目录加入 sys.path 并声明包名，让 from . import ... 正常解析
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sse_starlette.sse import EventSourceResponse

from . import (config, guard, logmask, metrics, orders, scheduler, sessions,
               store, summarize, trace)
from .agent import build_agent
from .schemas import ChatRequest, ClearRequest
from .tools.mall_client import NeedLoginError, resolve_member_id
from .tools.order_tools import current_member, current_session, current_token

# 日志总装配（M4.2 脱敏 + M4.3 traceId 注入/JSON 输出）：格式由 LOG_FORMAT 控制。
# 放这里而不是交给 uvicorn：uvicorn 只配置它自己的 logger，root 默认 WARNING，
# 不显式装配就会把应用自身的 INFO 日志（Redis 自检、定时索引、治理拦截）全吞掉。
# basicConfig 自带幂等判断，只在 root 无 handler 时生效。
logmask.setup()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 状态层自检：Redis 不通就快速失败，避免服务"起得来但会话全丢"的诡异故障
    store.assert_available()
    # M3.3 定时增量索引（APScheduler）：RAG_ENABLED=0 自动跳过；
    # 多 worker 下靠 ai:rag:lock 单飞，索引本身出问题只降级为"检索不到"，不影响对话
    scheduler.startup()
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(title="mall-ai-agent", version="0.3.0", lifespan=lifespan)

# 移动端 H5 跨域访问（M4.2 收紧）：白名单 + 私网正则。
# 原来放 "*" 是为了开发方便，但那是"任何网站都能用用户浏览器调这个服务"。
# 现在显式列出 portal-web 的端口，并用正则兜住 Vite 换端口/手机真机走局域网 IP
# 的联调场景（只放行回环与 RFC1918 私网，公网域名一律不在内）。
# token 在请求体里、不走 cookie，故不需要 allow_credentials。
_allow_all = config.CORS_ALLOW_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all else config.CORS_ALLOW_ORIGINS,
    allow_origin_regex=None if _allow_all else config.CORS_ALLOW_ORIGIN_REGEX,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", trace.TRACE_HEADER],
    # 浏览器默认只能读到少数「安全列表」响应头；不 expose 的话 JS 读不到 X-Trace-Id，
    # 前端就无法把它显示给用户（报障时凭编号定位整条链路）
    expose_headers=[trace.TRACE_HEADER],
)

# M4.3 链路追踪：解析/生成 traceId → set contextvar → 回写响应头。
# 必须用纯 ASGI 中间件（原因见 app/trace.py）。放在 CORS 之外层（后 add = 更外层），
# 这样连 CORS 预检的响应也会带上 traceId 头。
app.add_middleware(trace.TraceIdMiddleware)

# 懒加载单例：create_react_agent 编译出的图线程安全，可跨请求复用。
# 分两个槽位缓存：primary 用主模型；fallback 用降级模型
# （M4：全站日 token 超阈时切过去——服务降级，但不中断）
_agents: dict[str, object] = {}


def get_agent(degraded: bool = False):
    key = "fallback" if degraded else "primary"
    if key not in _agents:
        _agents[key] = build_agent(
            model=config.DEEPSEEK_FALLBACK_MODEL if degraded else None)
    return _agents[key]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/metrics")
def api_metrics(request: Request, token: str | None = None):
    """当日核心指标快照（M4.3）：工具成功率 / 拒答率 / 订单转化 / 延迟分位 / token 用量。

    默认开放（开发期直接 curl 看）。运维上该端点会泄露流量规模与错误率，
    生产应置于内网；若需暴露在公网，配 `METRICS_TOKEN` 后必须带令牌访问。
    """
    if not config.METRICS_ENABLED:
        return JSONResponse(status_code=404, content={"error": "metrics disabled"})
    if config.METRICS_TOKEN:
        got = token or request.headers.get("x-metrics-token") or ""
        # compare_digest 而非 ==：避开按字符提前返回的时序侧信道（顺手为之，成本为零）
        if not secrets.compare_digest(got, config.METRICS_TOKEN):
            return JSONResponse(status_code=403, content={"error": "forbidden"})
    return metrics.snapshot()


@app.get("/api/chat/history")
def chat_history(session_id: str = "default", token: str | None = None):
    """会话历史：前端重新进入聊天页时恢复 UI 记录（退出页面不再"丢记录"）"""
    member_id = resolve_member_id(token)
    return {"messages": sessions.export_history(session_id, member_id)}


@app.post("/api/chat/clear")
def chat_clear(req: ClearRequest):
    """清除会话：前端「清除会话」按钮调用。只清本会话的键，不动其它会话/业务缓存。"""
    sessions.clear(req.session_id or "default")
    return {"ok": True}


def _chunk_parts(chunk):
    """兼容不同 langgraph 版本 stream 产物的形态：(msg, meta) 元组 / 消息对象 / dict"""
    if isinstance(chunk, tuple):
        chunk = chunk[0]
    if isinstance(chunk, dict):
        return (chunk.get("type"), chunk.get("content", ""), chunk.get("tool_calls"), chunk.get("name"))
    return (
        getattr(chunk, "type", None),
        getattr(chunk, "content", ""),
        getattr(chunk, "tool_calls", None),
        getattr(chunk, "name", None),
    )


def _card(item: dict) -> dict:
    """从商品数据里只挑卡片需要的字段，保证发给前端的是干净数据"""
    return {
        "id": item.get("id"),
        "name": item.get("name") or "",
        "price": item.get("price"),
        "pic": item.get("pic") or "",
        "subTitle": item.get("subTitle") or "",
        "reason": item.get("reason") or "",  # P4 猜你喜欢：推荐理由
    }


def _parse_ids(content: str) -> list:
    """解析 show_products 工具回显的商品 id 列表，形如 '[28, 27]' 或 '["28","27"]'"""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    ids = []
    for v in data:
        try:
            ids.append(int(v))
        except (ValueError, TypeError):
            continue
    return ids


def _sse(event: str, payload: dict) -> dict:
    """sse-starlette 接受的格式：event + data。
    data 里也带上 type 字段，客户端只需解析 data 一个地方。"""
    payload = {"type": event, **payload}
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False)}


def _incoming(req: ChatRequest) -> list:
    """本轮用户输入以什么身份进入对话。

    默认是 HumanMessage（用户发言）。`as_system=True` 时包成 SystemMessage——
    前端点「确认下单」发来的「【系统指令】用户已确认下单，draft_id=xxx」必须走这条，
    否则 LLM 按 SYSTEM_PROMPT 规则 13 不认，不会调 place_order。
    """
    cls = SystemMessage if req.as_system else HumanMessage
    return [cls(content=req.message)]


def _delta(full: list, n_stored: int) -> list:
    """本轮**新增**的消息 = agent 返回的完整状态 去掉 前 n_stored 条。

    `n_stored` 是装配时**来自存储**的消息条数（`assemble_history` 的第二个返回值）。
    ⚠️ 不能拿 `len(prompt)` 当它——prompt 末尾还挂着本轮用户消息，**它还没入库**；
    若一并砍掉，用户那句话就永远丢了（这个坑已在 smoke_m15_e2e 里实测踩到过）。

    这样"本轮用户消息 + 工具消息 + 助手回复"都会被如实追加，
    而压缩视图（引用桩/折叠占位）因为不是"新增"，永远不会被写进事实源。
    """
    if len(full) > n_stored:
        return list(full[n_stored:])
    if len(full) < n_stored:  # pragma: no cover —— 理论上不会发生；宁可丢一轮也不写坏事实源
        logger.warning("agent 返回(%d) 少于装配前缀(%d)，本轮不落库以免污染历史", len(full), n_stored)
    return []


def _build_confirm(session_id: str, member_id, content: str) -> dict | None:
    """preview_order 结果 → 创建订单草稿，返回发给前端的确认卡片数据。

    草稿固定：购物车条目、默认收货地址、应付金额——LLM 无法修改；
    只有用户点击「确认下单」后 place_order 才能消费草稿。"""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    items = data.get("cartPromotionItemList") or []
    addrs = data.get("memberReceiveAddressList") or []
    calc = data.get("calcAmount") or {}
    if not items or not addrs:
        return None
    addr = next((a for a in addrs if a.get("defaultStatus") == 1), addrs[0])
    draft_id = orders.create_draft(session_id, member_id, {
        "cart_id": items[0]["id"],
        "address_id": addr["id"],
        "pay_amount": calc.get("payAmount"),
        "use_integration": calc.get("useIntegration") or 0,
    })
    return {
        "draftId": draft_id,
        "addressText": " ".join(str(addr.get(k) or "") for k in
                                ("name", "phoneNumber", "province", "city", "region", "detailAddress")),
        "items": [
            {
                "name": it.get("productName") or "",
                "pic": it.get("productPic") or "",
                "price": it.get("price"),
                "quantity": it.get("quantity"),
                "promotion": it.get("promotionMessage") or "",
            }
            for it in items
        ],
        "totalAmount": calc.get("totalAmount"),
        "promotionAmount": calc.get("promotionAmount"),
        "payAmount": calc.get("payAmount"),
    }


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request):
    """非流式版：调试/curl 用。会话记忆与流式版共用。

    同样过治理门禁——不因为是「调试接口」就留后门。
    """
    session_id = req.session_id or "default"
    trace_ses = trace.set_session(session_id)         # M4.3：后续日志带 sessionId
    t0 = time.perf_counter()
    member_id = resolve_member_id(req.token)          # M1：会话归属绑定会员
    usage = guard.TokenUsageCollector()               # M4：本轮 token 计量
    toolcb = metrics.ToolUsageCollector()             # M4.3：本轮工具成功/失败
    outcome, reply = "error", ""
    tok_ctx = ses_ctx = mem_ctx = None
    try:
        decision = guard.check(guard.ip_of(request), member_id)
        if not decision.allowed:
            outcome = "blocked"
            logger.info("治理拦截 surface=http code=%s", decision.code,
                        extra={"surface": "http", "code": decision.code})
            return JSONResponse(status_code=429, content=decision.as_event())
        try:
            agent = get_agent(degraded=decision.degraded)
        except RuntimeError as e:
            return JSONResponse(status_code=503, content={"error": str(e)})
        # 读路径：从事实源做分级装配（可能被压缩），只读、不落库
        sent, n_stored = sessions.assemble_history(session_id, member_id, _incoming(req))
        summarize.maybe_schedule(session_id, member_id)   # T3：惰性异步压摘要，不阻塞本轮
        tok_ctx = current_token.set(req.token or None)
        ses_ctx = current_session.set(session_id)
        mem_ctx = current_member.set(member_id)
        try:
            result = agent.invoke({"messages": sent},
                                  config={"callbacks": [usage, toolcb]})
        except NeedLoginError:
            # 未登录：返回 401 + 跳转指令，前端据此跳登录页
            outcome = "need_login"
            return JSONResponse(status_code=401, content={
                "need_login": True,
                "message": "请先登录后再进行此操作",
                "redirect": "/login",
            })
        except Exception as e:  # noqa: BLE001
            # M4：不回原始异常文本（可能含内网地址/连接串/栈帧），原文只进日志
            code, message = guard.classify_exception(e)
            logger.exception("非流式对话失败 code=%s", code)
            return JSONResponse(status_code=502, content={"error": message, "code": code})
        reply = result["messages"][-1].content
        # 写路径：只追加**本轮新增**的消息（含工具消息），保证下一轮「买第一款」能定位到商品 id
        sessions.append_turn(session_id, _delta(result.get("messages") or [], n_stored), member_id)
        # M1.5.4：达单会话上限才删最旧轮（且只删已被摘要覆盖的），不阻塞本轮
        summarize.maybe_trim(session_id, member_id)
        outcome = "ok"
        return {"reply": reply}
    finally:
        # 收尾统一记账：成功 / 拦截 / 异常都要留下指标与一条可检索的回合日志
        guard.record_usage(usage.total)               # M4：累加全站当日 token
        dur = (time.perf_counter() - t0) * 1000
        metrics.record_turn("http", outcome, dur, tools=toolcb.summary(),
                            answer=reply if outcome == "ok" else None)
        logger.info("turn end surface=http outcome=%s dur=%.0fms tokens=%d tools=%s",
                    outcome, dur, usage.total, toolcb.describe(),
                    extra={"surface": "http", "outcome": outcome,
                           "durationMs": round(dur), "tokens": usage.total,
                           "llmCalls": usage.calls, "tools": toolcb.describe()})
        if tok_ctx is not None:
            current_token.reset(tok_ctx)
        if ses_ctx is not None:
            current_session.reset(ses_ctx)
        if mem_ctx is not None:
            current_member.reset(mem_ctx)
        trace.reset_session(trace_ses)


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """SSE 流式版：H5 聊天页使用。

    事件类型：
      token     {content}     一段回复文本（前端追加渲染，实现打字机效果）
      tool      {name, args}  一次工具调用（前端显示「正在搜索商品…」）
      products  {items}       商品卡片（show_products 认可的真实搜索结果）
      product   {item}        单个商品详情卡片
      cart_added {cartId,...} 加购成功卡片
      confirm   {draftId,...} 订单确认卡片（preview_order 生成草稿，等用户点确认）
      order     {orderId,...} 下单成功卡片（用户确认后 place_order 的结果）
      citation  {items}       引用卡片（search_knowledge 命中的口碑来源；在本轮正文之后统一发）
      need_login {message}    未登录（前端弹登录引导，不算对话错误）
      done      {}            本轮结束
      error     {message, code}  出错。code 取值见 app/guard.py：
                               rate_limited / quota_exceeded / budget_exhausted（治理拦截）
                               llm_timeout / llm_busy / llm_unreachable / mall_unavailable …（调用异常）
    """
    # IP 在外层取好：Request 对象在响应开始后不保证还能访问，
    # 别放进 async generator 里用
    client_ip = guard.ip_of(request)

    async def event_stream():
        session_id = req.session_id or "default"
        trace_ses = trace.set_session(session_id)   # M4.3：后续日志带 sessionId
        t0 = time.perf_counter()
        member_id = resolve_member_id(req.token)   # M1：会话/草稿归属绑定会员
        usage = guard.TokenUsageCollector()        # M4：本轮 token 计量（含多次 LLM 调用）
        toolcb = metrics.ToolUsageCollector()      # M4.3：本轮工具成功/失败
        outcome, reply = "error", ""

        def _finish(oc: str, ans: str | None = None) -> None:
            """回合收尾：写指标 + 一条可检索日志 + 复位 trace。

            所有出口（正常 / 拦截 / 异常）都走这里，避免"某条 return 忘了记账"
            导致指标长期偏低——这类漏记很难在事后发现。
            """
            guard.record_usage(usage.total)        # M4：全站当日 token（失败轮也计）
            dur = (time.perf_counter() - t0) * 1000
            metrics.record_turn("sse", oc, dur, tools=toolcb.summary(), answer=ans)
            logger.info("turn end surface=sse outcome=%s dur=%.0fms tokens=%d tools=%s",
                        oc, dur, usage.total, toolcb.describe(),
                        extra={"surface": "sse", "outcome": oc,
                               "durationMs": round(dur), "tokens": usage.total,
                               "llmCalls": usage.calls, "tools": toolcb.describe()})
            trace.reset_session(trace_ses)

        # M4 治理门禁：超限回 error 事件（而不是断流）——前端已有 error 分支，
        # 零改动即可展示；code 字段留给将来做差异化 UI
        decision = guard.check(client_ip, member_id)
        if not decision.allowed:
            logger.info("治理拦截 surface=sse code=%s", decision.code,
                        extra={"surface": "sse", "code": decision.code})
            yield _sse("error", decision.as_event())
            _finish("blocked")
            return

        try:
            agent = get_agent(degraded=decision.degraded)
        except RuntimeError as e:
            yield _sse("error", {"message": str(e), "code": "llm_unconfigured"})
            _finish("error")
            return
        if decision.degraded:
            # 成本上限触发 → 本轮换轻量模型。不显式记一条，就只剩「回答怎么变差了」的体感
            logger.info("成本上限触发，本轮降级模型 surface=sse",
                        extra={"surface": "sse", "degraded": True})
        # 读路径：分级装配（可能被压缩），只读；n_stored 供写路径算"本轮新增"
        sent, n_stored = sessions.assemble_history(session_id, member_id, _incoming(req))
        summarize.maybe_schedule(session_id, member_id)   # T3：惰性异步压摘要，不阻塞本轮

        # ContextVar 把会话 token/member 传进无状态工具（langchain 工具不能带 session 参数）
        tok_ctx = current_token.set(req.token or None)
        ses_ctx = current_session.set(session_id)
        mem_ctx = current_member.set(member_id)
        try:
            full_reply = ""
            # 本轮搜索累计的商品 id → 原始数据。卡片只展示 show_products 认可的商品，
            # 这样卡片与回复文字永远一致，LLM 编造不出卡片，也不会展示无关商品
            found_items: dict = {}
            # 本轮命中的引用（search_knowledge）→ 攒起来，等正文流完再发（见循环末尾）
            cites_acc: list = []
            # values 流：每个节点执行后的完整状态，最后一帧含全部消息（含工具消息），
            # 用它覆盖会话历史，保证跨轮次上下文完整（「买第一款」依赖工具消息里的 id）
            final_state = None
            async for mode, chunk in agent.astream(
                    {"messages": sent},
                    stream_mode=["messages", "values"],
                    config={"callbacks": [usage, toolcb]},   # M4 计量 token / M4.3 统计工具
            ):
                if mode == "values":
                    final_state = chunk
                    continue
                msg_type, content, tool_calls, tool_name = _chunk_parts(chunk)
                if tool_calls:
                    for tc in tool_calls:
                        # 流式下 tool_calls 是碎片：第一个碎片带 name（args 为空），
                        # 后续碎片带 args（name 为空）→ 只在 name 出现时发一次事件
                        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        if name:
                            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None)
                            args_str = "" if not args or args == "{}" else str(args)
                            yield _sse("tool", {"name": name, "args": args_str})
                # 工具执行结果 → 提取真实商品数据
                if msg_type == "tool" and content and tool_name:
                    if tool_name == "search_products":
                        # 先记录搜索结果，展示哪些卡片由 LLM 调 show_products 决定
                        try:
                            data = json.loads(content)
                        except (json.JSONDecodeError, TypeError):
                            data = []
                        for it in data if isinstance(data, list) else []:
                            if isinstance(it, dict) and it.get("id") is not None:
                                found_items[int(it["id"])] = it
                    elif tool_name == "recommend_for_me":
                        # 猜你喜欢：与搜索结果同一套 found_items 过滤链路
                        try:
                            data = json.loads(content)
                        except (json.JSONDecodeError, TypeError):
                            data = []
                        for it in data if isinstance(data, list) else []:
                            if isinstance(it, dict) and it.get("id") is not None:
                                found_items[int(it["id"])] = it
                    elif tool_name == "show_products":
                        # 只展示 LLM 认可的（且真实存在于搜索结果里的）商品
                        items = [found_items[i] for i in _parse_ids(content) if i in found_items][:5]
                        if items:
                            yield _sse("products", {"items": [_card(i) for i in items]})
                    elif tool_name == "get_product_detail":
                        try:
                            data = json.loads(content)
                        except (json.JSONDecodeError, TypeError):
                            data = {}
                        product = data.get("product") if isinstance(data, dict) else None
                        if isinstance(product, dict) and product.get("id"):
                            yield _sse("product", {"item": _card(product)})
                    elif tool_name == "add_to_cart":
                        # 加购成功 → 渲染「已加入购物车」卡片
                        try:
                            data = json.loads(content)
                        except (json.JSONDecodeError, TypeError):
                            data = {}
                        if isinstance(data, dict) and data.get("cartId"):
                            yield _sse("cart_added", {
                                "cartId": data.get("cartId"),
                                "productName": data.get("productName") or "",
                                "price": data.get("price"),
                                "quantity": data.get("quantity"),
                            })
                    elif tool_name == "preview_order":
                        # 生成订单草稿 + 确认卡片，等用户点「确认下单」
                        confirm = _build_confirm(session_id, member_id, content)
                        if confirm:
                            yield _sse("confirm", confirm)
                    elif tool_name == "place_order":
                        # 用户已确认，place_order 成功 → 下单成功卡片
                        try:
                            order = json.loads(content)
                        except (json.JSONDecodeError, TypeError):
                            order = {}
                        if isinstance(order, dict) and order.get("id"):
                            yield _sse("order", {
                                "orderId": order.get("id"),
                                "orderSn": order.get("orderSn"),
                                "payAmount": order.get("payAmount"),
                            })
                    elif tool_name == "search_knowledge":
                        # 语义道检索命中 → 引用卡片（商品名 + 星级 + 评价数 + 可回跳）
                        # 只推前端可展示字段：**不含 score / indexedAt**（内部标识不外泄）
                        try:
                            kb = json.loads(content)
                        except (json.JSONDecodeError, TypeError):
                            kb = {}
                        if isinstance(kb, dict) and kb.get("hit"):
                            cites = [
                                {
                                    "productId": it.get("productId"),
                                    "name": it.get("name") or "",
                                    "source": it.get("docType") or "",
                                    "starAvg": it.get("starAvg"),
                                    "reviewCount": it.get("reviewCount"),
                                }
                                for it in (kb.get("items") or [])
                                if it.get("productId")
                            ]
                            cites_acc.extend(cites)
                # 只推 AI 的文本；tool 消息(原始JSON)不给前端
                if msg_type != "tool" and content:
                    full_reply += content
                    yield _sse("token", {"content": content})
            # 引用卡片（M3.4）统一放在正文**之后**：与「参考资料」的阅读习惯一致，
            # 也避免卡片把「过渡语 → 正式回答」从中截断。
            # 工具返回时只攒进 cites_acc，等本轮 token 流跑完（回答已完整流给用户）再发一次。
            if cites_acc:
                yield _sse("citation", {"items": cites_acc})
            # 写路径：只追加本轮新增的消息；拿不到 final_state 时退回"用户问 + 助手答"两条
            if isinstance(final_state, dict) and isinstance(final_state.get("messages"), list):
                sessions.append_turn(session_id, _delta(final_state["messages"], n_stored), member_id)
            else:
                sessions.append_turn(session_id, _incoming(req) + [AIMessage(content=full_reply)],
                                     member_id)
            # M1.5.4：达单会话上限才删最旧轮（且只删已被摘要覆盖的），不阻塞本轮
            summarize.maybe_trim(session_id, member_id)
            reply = full_reply
            outcome = "ok"
            yield _sse("done", {})
        except NeedLoginError:
            outcome = "need_login"
            # 未登录：发 need_login 事件，前端收到后跳登录页（不是对话错误）
            # 不存历史——登录后用户重发该条消息即可，避免半截状态
            yield _sse("need_login", {
                "message": "请先登录后再进行此操作",
                "redirect": "/login",
                "return_to": "/chat",
            })
        except Exception as e:  # noqa: BLE001 —— 流式内任何异常都要回给前端而不是断开
            # M4：面向用户只给友好文案；原始异常（可能含内网地址/连接串/文件路径）只进日志
            code, message = guard.classify_exception(e)
            logger.exception("流式对话失败 code=%s", code)
            yield _sse("error", {"message": message, "code": code})
        finally:
            _finish(outcome, reply if outcome == "ok" else None)
            current_token.reset(tok_ctx)
            current_session.reset(ses_ctx)
            current_member.reset(mem_ctx)

    return EventSourceResponse(event_stream())


# PyCharm 里右键直接 Run 入口：python -m app.main 或 python app/main.py
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8090, reload=False)
