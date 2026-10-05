"""AI Agent 服务入口（FastAPI）

启动：.venv\\Scripts\\python -m uvicorn app.main:app --reload --port 8090

接口：
  GET  /health           健康检查
  POST /api/chat         非流式（调试用，session 有记忆）
  POST /api/chat/stream  SSE 流式（H5 聊天页用，session 有记忆）
"""
import json
import logging
import sys
from pathlib import Path

# 支持两种运行方式：
# 1) 模块方式（命令行）：python -m app.main 或 uvicorn app.main:app
# 2) 脚本方式（PyCharm 右键 Run 'main'）：__package__ 为 None，相对导入会失败，
#    这里把项目根目录加入 sys.path 并声明包名，让 from . import ... 正常解析
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sse_starlette.sse import EventSourceResponse

from . import orders, sessions, store, summarize
from .agent import build_agent
from .schemas import ChatRequest, ClearRequest
from .tools.mall_client import NeedLoginError, resolve_member_id
from .tools.order_tools import current_member, current_session, current_token

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 状态层自检：Redis 不通就快速失败，避免服务"起得来但会话全丢"的诡异故障
    store.assert_available()
    yield


app = FastAPI(title="mall-ai-agent", version="0.3.0", lifespan=lifespan)

# 移动端 H5 跨域访问：开发期放开所有源（vite 端口可能变化/手机真机用局域网 IP），
# token 在请求体里、不走 cookie，无 CSRF 风险；P6 加固时再收紧白名单
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 懒加载单例：create_react_agent 编译出的图是线程安全的，可跨请求复用
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


@app.get("/health")
def health():
    return {"status": "ok"}


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
def chat(req: ChatRequest):
    """非流式版：调试/curl 用。会话记忆与流式版共用。"""
    try:
        agent = get_agent()
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"error": str(e)})
    session_id = req.session_id or "default"
    member_id = resolve_member_id(req.token)          # M1：会话归属绑定会员
    # 读路径：从事实源做分级装配（可能被压缩），只读、不落库
    sent, n_stored = sessions.assemble_history(session_id, member_id, _incoming(req))
    summarize.maybe_schedule(session_id, member_id)   # T3：惰性异步压摘要，不阻塞本轮
    tok_ctx = current_token.set(req.token or None)
    ses_ctx = current_session.set(session_id)
    mem_ctx = current_member.set(member_id)
    try:
        result = agent.invoke({"messages": sent})
    except NeedLoginError:
        # 未登录：返回 401 + 跳转指令，前端据此跳登录页
        return JSONResponse(status_code=401, content={
            "need_login": True,
            "message": "请先登录后再进行此操作",
            "redirect": "/login",
        })
    finally:
        current_token.reset(tok_ctx)
        current_session.reset(ses_ctx)
        current_member.reset(mem_ctx)
    reply = result["messages"][-1].content
    # 写路径：只追加**本轮新增**的消息（含工具消息），保证下一轮「买第一款」能定位到商品 id
    sessions.append_turn(session_id, _delta(result.get("messages") or [], n_stored), member_id)
    # M1.5.4：达单会话上限才删最旧轮（且只删已被摘要覆盖的），不阻塞本轮
    summarize.maybe_trim(session_id, member_id)
    return {"reply": reply}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式版：H5 聊天页使用。

    事件类型：
      token    {content}     一段回复文本（前端追加渲染，实现打字机效果）
      tool     {name, args}  一次工具调用（前端显示「正在搜索商品…」）
      products {items}       商品卡片（show_products 认可的真实搜索结果）
      product  {item}        单个商品详情卡片
      confirm  {draftId,...} 订单确认卡片（preview_order 生成草稿，等用户点确认）
      order    {orderId,...} 下单成功卡片（用户确认后 place_order 的结果）
      done     {}            本轮结束
      error    {message}     出错（如 mall 接口不可用 / LLM 调用失败）
    """
    async def event_stream():
        try:
            agent = get_agent()
        except RuntimeError as e:
            yield _sse("error", {"message": str(e)})
            return

        session_id = req.session_id or "default"
        member_id = resolve_member_id(req.token)   # M1：会话/草稿归属绑定会员
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
            # values 流：每个节点执行后的完整状态，最后一帧含全部消息（含工具消息），
            # 用它覆盖会话历史，保证跨轮次上下文完整（「买第一款」依赖工具消息里的 id）
            final_state = None
            async for mode, chunk in agent.astream({"messages": sent}, stream_mode=["messages", "values"]):
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
                # 只推 AI 的文本；tool 消息(原始JSON)不给前端
                if msg_type != "tool" and content:
                    full_reply += content
                    yield _sse("token", {"content": content})
            # 写路径：只追加本轮新增的消息；拿不到 final_state 时退回"用户问 + 助手答"两条
            if isinstance(final_state, dict) and isinstance(final_state.get("messages"), list):
                sessions.append_turn(session_id, _delta(final_state["messages"], n_stored), member_id)
            else:
                sessions.append_turn(session_id, _incoming(req) + [AIMessage(content=full_reply)],
                                     member_id)
            # M1.5.4：达单会话上限才删最旧轮（且只删已被摘要覆盖的），不阻塞本轮
            summarize.maybe_trim(session_id, member_id)
            yield _sse("done", {})
        except NeedLoginError:
            # 未登录：发 need_login 事件，前端收到后跳登录页（不是对话错误）
            # 不存历史——登录后用户重发该条消息即可，避免半截状态
            yield _sse("need_login", {
                "message": "请先登录后再进行此操作",
                "redirect": "/login",
                "return_to": "/chat",
            })
        except Exception as e:  # noqa: BLE001 —— 流式内任何异常都要回给前端而不是断开
            yield _sse("error", {"message": f"服务出错: {e}"})
        finally:
            current_token.reset(tok_ctx)
            current_session.reset(ses_ctx)
            current_member.reset(mem_ctx)

    return EventSourceResponse(event_stream())


# PyCharm 里右键直接 Run 入口：python -m app.main 或 python app/main.py
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8090, reload=False)
