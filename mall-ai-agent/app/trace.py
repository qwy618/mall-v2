"""链路追踪（M4.3）：每个请求一个 traceId，贯穿该请求产生的所有日志。

为什么需要 traceId：

一次对话会打出多条日志（治理决策、装配、每次工具调用、每轮 LLM、回合收尾），
并发下这些日志**交错**在一起，没有共同标识就没法把「这一堆」归给「那一次请求」。
`tail -f` 看单机日志时这一点不痛不痒，一旦多条会话并发、或日志进了采集系统，
没有 traceId 等于没法排查。

## 三个设计点

**1. 用 contextvar 传播，而不是逐层传参。**
日志散落在一堆不相关的函数/工具里，不可能给每个 `logger.info` 都补一个 trace_id 参数。
contextvar 的特性正好：在同一调用链/协程里自动可见，请求结束 reset，互不串味。

**2. 中间件必须是纯 ASGI，不能用 `@app.middleware("http")`。**
后者基于 `BaseHTTPMiddleware`，会把下游应用放进**子 task**跑；在部分 Starlette
版本里 contextvar 的 set 不会可靠地下传，症状是「中间件里明明 set 了 traceId，
业务日志里却取到空」——这种坑极难查（代码看起来完全正确）。纯 ASGI 中间件与业务
在同一 context，没有这个问题。

**3. 外部传入的 traceId 必须过白名单。**
它会原样写进日志行与响应头。若放任 `\n`、引号、超长串进来，就是**日志注入**：
伪造出假的日志行、或在 JSON 日志里撑破结构。只接受 `[A-Za-z0-9_.-]{1,64}`。
"""
from __future__ import annotations

import contextvars
import re
import secrets

# 上游（portal-web / 网关）可透传这个头做跨服务串联；本服务也会回写同名响应头
TRACE_HEADER = "X-Trace-Id"

# 白名单：足够覆盖 uuid/hex/自增编号等常见形态，同时挡掉换行与引号
_VALID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
_session_id: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="")


def new_id() -> str:
    """12 位 hex：单请求内够唯一，肉眼扫日志时也不至于长到没法读。"""
    return secrets.token_hex(6)


def sanitize(raw: str | None) -> str:
    """外部 traceId 白名单校验；不合法一律返回空串（由调用方决定是否补发新值）。"""
    if not raw:
        return ""
    raw = raw.strip()
    return raw if _VALID.match(raw) else ""


def set_trace(trace_id: str | None) -> contextvars.Token:
    """set 并返回 token 供 finally 里 reset —— 必须 reset，否则协程复用会串号。"""
    return _trace_id.set(sanitize(trace_id) or new_id())


def get_trace() -> str:
    return _trace_id.get()


def reset(token: contextvars.Token) -> None:
    _trace_id.reset(token)


def set_session(sid: str | None) -> contextvars.Token:
    return _session_id.set(sid or "")


def get_session() -> str:
    return _session_id.get()


def reset_session(token: contextvars.Token) -> None:
    _session_id.reset(token)


class TraceIdMiddleware:
    """纯 ASGI 中间件：解析/生成 traceId → set contextvar → 回写响应头。

    不做访问日志。原因：本服务的主接口是 SSE，`StreamingResponse` 的响应对象在
    **首字节**发出后中间件就返回了，此时测到的耗时只到「首字节」而不是「回合结束」，
    记下来反而误导。真正的回合耗时由业务侧在流水线收尾时记（见 main.py）。
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        raw = ""
        for k, v in scope.get("headers") or []:
            if k == b"x-trace-id":
                raw = v.decode("latin-1")     # 头部是 latin-1，这里只做初步解码
                break
        trace_id = sanitize(raw) or new_id()
        token = _trace_id.set(trace_id)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # 回写给前端/网关：用户报障时报这个编号，运维能一键捞出整条链路
                headers = list(message.get("headers") or [])
                headers.append((TRACE_HEADER.lower().encode("latin-1"),
                                trace_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            _trace_id.reset(token)
