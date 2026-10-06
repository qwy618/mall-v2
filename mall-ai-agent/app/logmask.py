"""日志脱敏（M4.2）——日志与异常堆栈里绝不出现凭据。

为什么需要它：

1. `logger.exception` 会把**完整堆栈**写进日志。httpx 的 HTTPError 自带请求 URL，
   第三方 SDK 的报错里常带请求头（含 `Authorization`）。一旦 DEBUG 打开、
   或有人照着"把异常打出来"排查，token 就落进日志文件了 —— 而日志是最容易被
   顺手复制、发群、贴 issue 的东西。
2. `guard.classify_exception` 已经保证**用户看到**的文案不含细节；
   本模块补的是另一半：**运维看到的**日志同样不含凭据。

实现方式：包住已有 handler 的 formatter，对**最终格式化字符串**做替换。
选择这个位置而不是 Filter，是因为 Filter 只能改 `record.msg`/`record.args`，
而 `exc_info`（异常堆栈文本）由 Formatter 在最后一步渲染 —— 想连堆栈一起脱敏，
就必须拦在 Formatter 这一层。
"""
from __future__ import annotations

import logging
import re

from . import config

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


class MaskingFormatter(logging.Formatter):
    """在 Formatter 收尾处脱敏 —— 这样 exc_info / stack_info 里的文本也会被覆盖。"""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        return mask(super().format(record))


_DEFAULT_FMT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

# 这些库在 DEBUG 下会打印请求头（含 Authorization）与完整请求体。
# 服务本身只需要它们报错，不需要它们唠叨。
#
# ⚠️ 注意 `httpx2` / `httpcore2`：新版 openai SDK 内置了一个**改名的 httpx 分支**
# （`site-packages/httpx2/_alias.py` 会把 `import httpx` 指向它），它的 logger 名
# 因此是 `httpx2` 而不是 `httpx` —— 只写 `httpx` 会漏掉它，实测日志里会照常出现
# "HTTP Request: POST https://api.deepseek.com/chat/completions"。别再删这两个名字。
_NOISY_LOGGERS = ("httpx", "httpcore", "httpx2", "httpcore2",
                  "urllib3", "openai", "qdrant_client")


def install(fmt: str | None = None) -> None:
    """把脱敏 formatter 装到 root 的所有 handler 上，并压低三方库日志级别。

    幂等：重复调用只是再包一层同样的 formatter，不会叠加替换规则。
    """
    fmt = fmt or _DEFAULT_FMT
    root = logging.getLogger()
    if not root.handlers:                     # 调用方还没配日志（如脚本场景）
        logging.basicConfig(level=logging.INFO, format=fmt)

    for h in root.handlers:
        if config.LOG_REDACT:
            h.setFormatter(MaskingFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
        else:
            h.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    for name in _NOISY_LOGGERS:
        lg = logging.getLogger(name)
        # 已经是更高级别（如 ERROR）就别降回来
        if lg.level in (logging.NOTSET, logging.DEBUG, logging.INFO):
            lg.setLevel(logging.WARNING)


def status() -> dict:
    """诊断用：当前是否开启脱敏、生效了几条规则、三方库被压到哪一级。"""
    return {
        "redact": config.LOG_REDACT,
        "rules": len(_RULES),
        "noisyLoggers": {n: logging.getLevelName(logging.getLogger(n).level)
                         for n in _NOISY_LOGGERS},
    }
