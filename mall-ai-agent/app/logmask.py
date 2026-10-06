"""日志：脱敏（M4.2）+ 结构化输出与 traceId 注入（M4.3）—— 合成一个装配点。

为什么需要它：

1. `logger.exception` 会把**完整堆栈**写进日志。httpx 的 HTTPError 自带请求 URL，
   第三方 SDK 的报错里常带请求头（含 `Authorization`）。一旦 DEBUG 打开、
   或有人照着"把异常打出来"排查，token 就落进日志文件了 —— 而日志是最容易被
   顺手复制、发群、贴 issue 的东西。
2. `guard.classify_exception` 已经保证**用户看到**的文案不含细节；
   本模块补的是另一半：**运维看到的**日志同样不含凭据。
3. M4.3 起还要解决「一堆并发请求的日志分不清谁是谁」：每条日志注入 `traceId`
   （以及 `sessionId`），并可按需切成 JSON 行输出给采集系统。

## 脱敏拦在哪一层（M4.2 的结论）

包住已有 handler 的 formatter，对**最终格式化字符串**做替换。
不选 Filter：Filter 只能改 `record.msg`/`record.args`，而 `exc_info`（异常堆栈文本）
由 Formatter 在最后一步渲染 —— 想连堆栈一起脱敏，就必须拦在 Formatter 这一层。

## 但 JSON 模式下这条结论要拐个弯（M4.3 的坑）

`mask()` 的规则是「键名 + 分隔符 + 值」整体替换：`token=abc` → `token=***`，
对纯文本无副作用。可一旦把它套在**已经序列化好的 JSON 行**上：
`{"token": "abc"}` 会被替换成 `{"token": ***}` —— 值两侧的引号被规则一起吃掉，
整行 JSON 直接失效。

所以 JSON 模式下改为：**逐字段 mask 值 → 再 json.dumps**。脱敏与「结构合法」两不误。
"""
from __future__ import annotations

import json
import logging
import re

from . import config, trace

# 最终替换结果统一用它，便于在日志里一眼看出"这里被脱敏了"
MASK = "***"

# 顺序有意义：先处理带键名的（token=xxx），再处理裸串（eyJxxx / sk-xxx）
_RULES: list[tuple[re.Pattern[str], str]] = [
    # Authorization: Bearer <jwt>  /  "Bearer eyJ..."
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{6,}"), f"Bearer {MASK}"),
    # 带键名的常见凭据（查询串 / JSON / Python dict repr 都能覆盖）。
    # 键名两侧的引号要容忍单双两种：JSON 是 "key":"v"，Python repr 是 'key': 'v'
    (re.compile(r"(?i)\b(token|password|passwd|pwd|secret|api[_-]?key|apikey|access[_-]?key)"
                r"([\"']?\s*[:=]\s*[\"']?)([^\s&\"',;)}\]]+)"),
     rf"\1\2{MASK}"),
    # JWT（mall 的登录 token 就是三段式）——无键名裸串也要拦住
    (re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]+"), f"{MASK}"),
    # DeepSeek / OpenAI 风格密钥
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"), f"{MASK}"),
    # GitHub PAT（本项目开发期会用到；顺手一起拦）
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{16,})"), f"{MASK}"),
    # 手机号（会员 PII）。前后加数字断言：19 位雪花订单号不会被拦腰截断成手机号
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "1**********"),
]


def mask(text: str) -> str:
    """纯函数：把一行/一段文本里的凭据替换掉。验收脚本直接测它。"""
    if not text:
        return text
    out = text
    for pat, repl in _RULES:
        out = pat.sub(repl, out)
    return out


_DEFAULT_TEXT_FMT = "%(asctime)s %(levelname)s [%(name)s] [t=%(trace_id)s] %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


class _ContextFormatter(logging.Formatter):
    """给每条 LogRecord 补 trace_id / session_id 两个字段。

    用 `setdefault` 而非直接赋值：调用方若已显式传 `extra={"trace_id": ...}`
    （如后台线程/定时任务没有请求上下文），以它为准。
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        record.__dict__.setdefault("trace_id", trace.get_trace() or "-")
        record.__dict__.setdefault("session_id", trace.get_session() or "-")
        return super().format(record)


class MaskingFormatter(_ContextFormatter):
    """文本模式：在 Formatter 收尾处脱敏 —— exc_info / stack_info 也被覆盖。"""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        return mask(super().format(record))


# LogRecord 的标准属性集合（用于把「调用方 extra 传的字段」挑出来）。
# 动态取而非手抄：Python 版本间会增删（如 3.12 的 taskName）。
_STD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message", "asctime", "taskName",
}


class JsonFormatter(_ContextFormatter):
    """一行一条 JSON。字段固定，便于采集系统按字段建索引、按 level/traceId 检索。

    🔴 绝不调用 `mask()` 处理最终字符串（原因见模块 docstring）：对**每个字符串值**
    单独 mask，再交给 `json.dumps`，这样脱敏不会破坏 JSON 结构。
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict = {
            "ts": self.formatTime(record, _DATE_FMT),
            "level": record.levelname,
            "logger": record.name,
            "msg": mask(record.getMessage()),
            "traceId": mask(str(record.__dict__.get("trace_id")
                               or trace.get_trace() or "-")),
            "sessionId": mask(str(record.__dict__.get("session_id")
                                 or trace.get_session() or "-")),
        }
        # 调用方 extra 传进来的结构化字段（如 tool=..., outcome=...）：一并入 JSON，
        # 这正是「结构化日志」的价值 —— tool 名、耗时、token 都成为可检索字段。
        for k, v in record.__dict__.items():
            if k in _STD_ATTRS or k in payload or k.startswith("_"):
                continue
            payload[k] = mask(v) if isinstance(v, str) else v
        if record.exc_info:
            payload["exc"] = mask(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


# 这些库在 DEBUG 下会打印请求头（含 Authorization）与完整请求体。
# 服务本身只需要它们报错，不需要它们唠叨。
#
# ⚠️ 注意 `httpx2` / `httpcore2`：新版 openai SDK 内置了一个**改名的 httpx 分支**
# （`site-packages/httpx2/_alias.py` 会把 `import httpx` 指向它），它的 logger 名
# 因此是 `httpx2` 而不是 `httpx` —— 只写 `httpx` 会漏掉它，实测日志里会照常出现
# "HTTP Request: POST https://api.deepseek.com/chat/completions"。别再删这两个名字。
_NOISY_LOGGERS = ("httpx", "httpcore", "httpx2", "httpcore2",
                  "urllib3", "openai", "qdrant_client")

# uvicorn 自带的 logger（access/error）默认不进 root，各自带 handler。
# JSON 模式下顺手把它们也换成同一 formatter，否则输出里会混进非 JSON 的裸行，
# 采集系统解析到一半报错（uvicorn 启动横幅仍是文本，那部分无害）。
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def _build_formatter(fmt_kind: str, fmt: str | None):
    kind = (fmt_kind or "text").lower()
    if kind == "json":
        return JsonFormatter()
    text_fmt = fmt or _DEFAULT_TEXT_FMT
    if config.LOG_REDACT:
        return MaskingFormatter(text_fmt, datefmt=_DATE_FMT)
    return _ContextFormatter(text_fmt, datefmt=_DATE_FMT)


def install(fmt: str | None = None, fmt_kind: str | None = None) -> None:
    """把 (脱敏 + trace 注入) 的 formatter 装到 root / uvicorn 的 handler 上，
    并压低三方库日志级别。

    fmt_kind: "text" | "json"，缺省取 `config.LOG_FORMAT`。幂等：重复调用不会叠加替换。
    """
    kind = (fmt_kind or config.LOG_FORMAT or "text").lower()
    root = logging.getLogger()
    if not root.handlers:                     # 调用方还没配日志（如脚本场景）
        logging.basicConfig(level=config.LOG_LEVEL, format=_DEFAULT_TEXT_FMT)

    formatter = _build_formatter(kind, fmt)
    for h in root.handlers:
        h.setFormatter(formatter)

    # uvicorn 的 logger 只在「有 handler 且非传递到 root」时才需要单独换；
    # 无 handler 的会向上冒泡到 root，由上面的 formatter 处理，别重复设置。
    for name in _UVICORN_LOGGERS:
        for h in logging.getLogger(name).handlers:
            h.setFormatter(formatter)

    for name in _NOISY_LOGGERS:
        lg = logging.getLogger(name)
        # 已经是更高级别（如 ERROR）就别降回来
        if lg.level in (logging.NOTSET, logging.DEBUG, logging.INFO):
            lg.setLevel(logging.WARNING)


def setup() -> None:
    """进程启动时的日志总装配：basicConfig + install。main.py 只调这一个。"""
    kind = (config.LOG_FORMAT or "text").lower()
    if not logging.getLogger().handlers:
        logging.basicConfig(level=config.LOG_LEVEL)
    install(fmt_kind=kind)


def status() -> dict:
    """诊断用：当前输出格式、是否脱敏、生效了几条规则、三方库被压到哪一级。"""
    return {
        "format": (config.LOG_FORMAT or "text").lower(),
        "level": logging.getLevelName(logging.getLogger().level),
        "redact": config.LOG_REDACT,
        "rules": len(_RULES),
        "noisyLoggers": {n: logging.getLevelName(logging.getLogger(n).level)
                         for n in _NOISY_LOGGERS},
    }
