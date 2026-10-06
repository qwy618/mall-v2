"""治理层（M4）：限流 / 配额 / 成本上限 / 异常友好化。

## 三条设计原则

**1. 计数必须在 Redis。**
进程内计数（模块级 dict、类属性）在多 worker 下等于「每个 worker 各算一份配额」——
配 10 次/分、起 2 个 worker，实际就是 20 次/分，且每次重启清零。
这与 M1「状态一律外置」是同一条铁律，理由也一样。

**2. 挡 / 限 / 让 是三种不同动作，不要混成一个「拒绝」。**

| 手段 | 窗口 | 动作 | 用户感知 |
| --- | --- | --- | --- |
| 限流 | 分钟 | 挡在门外 | 等几秒再来 |
| 配额 | 日 | 限制总量 | 今天没了，明天再来 |
| 成本上限 | 日（全站） | 降级服务 | 换轻量模型，照常可用 |

三者文案必须区分。用户看到「请稍后再试」却要等到明天——这是很糟的体验。

**3. fail-open：计数出错时放行并告警。**
治理是「防滥用」，不该成为新的单点故障——为了限流把正常用户挡在门外，
代价远大于放过几次请求。🔴 这与 store.py 的「Redis 不可用要大声报错」不矛盾：
那条约束**数据面**（会话丢了不可接受），这条约束**控制面**（少限几次没关系）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import redis
from langchain_core.callbacks import BaseCallbackHandler

from . import config, store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- 身份

def ip_of(request) -> str:
    """取客户端 IP。将来若置于反向代理之后，应改为优先读 X-Forwarded-For 首段，
    否则所有用户会共享代理的 IP、被当成同一个人限流。"""
    try:
        return request.client.host or "unknown"
    except AttributeError:      # 验收脚本里传 None 等非 Request 对象
        return "unknown"


def subject_of(client_ip: str, member_id) -> tuple[str, bool]:
    """返回 (Redis 键里的身份标识, 是否会员)。

    游客**不能**用 session_id 当身份——那是前端生成的，localStorage 里换一个就绕过了
    限流。IP 虽然也不完美（NAT 后多人共享出口 IP、换 IP 可绕过），但成本高得多。
    """
    if member_id:
        return f"m{member_id}", True
    return f"ip{client_ip}", False


# ---------------------------------------------------------------- 门禁决策

@dataclass
class Decision:
    allowed: bool
    code: str = ""              # rate_limited / quota_exceeded / budget_exhausted
    message: str = ""           # 面向用户的中文文案
    degraded: bool = False      # True → 本轮改用 fallback 模型
    rate: int = 0               # 当前分钟桶计数（诊断用）
    quota: int = 0              # 当日计数（诊断用）

    def as_event(self) -> dict:
        """SSE error 事件的 payload（错误码让前端将来可做差异化处理）。"""
        return {"message": self.message, "code": self.code}


def check(client_ip: str, member_id) -> Decision:
    """请求入口的门禁。先限流（便宜）再配额（较贵），超限即返回。"""
    if not config.GUARD_ENABLED:
        return Decision(allowed=True)

    subj, is_member = subject_of(client_ip, member_id)
    try:
        rate_limit = config.RATE_PER_MIN_MEMBER if is_member else config.RATE_PER_MIN_GUEST
        n_rate = store.hit_rate(subj)
        if n_rate > rate_limit:
            return Decision(False, "rate_limited",
                            "提问有点快，请稍等几秒再试", rate=n_rate)

        quota_limit = config.QUOTA_PER_DAY_MEMBER if is_member else config.QUOTA_PER_DAY_GUEST
        n_quota = store.hit_quota(subj)
        if n_quota > quota_limit:
            return Decision(False, "quota_exceeded",
                            "今天的咨询次数用完啦，明天再来找我吧", quota=n_quota)

        over_budget = store.peek_tokens() >= config.DAILY_TOKEN_LIMIT
    except redis.RedisError as e:
        # fail-open：控制面故障不该影响业务可用性
        logger.warning("治理计数失败，放行本次请求（fail-open）：%s", e)
        return Decision(allowed=True)

    if over_budget:
        if not config.DEEPSEEK_FALLBACK_MODEL:
            # 没有可降级的模型 → 只能停。宁可拒答，不可烧穿预算。
            return Decision(False, "budget_exhausted",
                            "今天的服务额度已用完，明天再来找我吧")
        return Decision(True, degraded=True, rate=n_rate, quota=n_quota)

    return Decision(True, rate=n_rate, quota=n_quota)


# ---------------------------------------------------------------- 异常友好化

# 用**类名**匹配而不是 isinstance：这样不 import openai 也能工作，
# 而且 MRO 遍历能覆盖子类（如 openai 版本升级改了继承结构）。
_ERROR_MAP: dict[str, tuple[str, str]] = {
    "APITimeoutError":    ("llm_timeout",      "AI 响应有点慢，请稍后再试"),
    "RateLimitError":     ("llm_busy",         "当前咨询的人有点多，请稍后再试"),
    "APIConnectionError": ("llm_unreachable",  "AI 服务暂时连不上，请稍后再试"),
    "AuthenticationError": ("llm_auth",        "AI 服务配置有误，请联系管理员"),
}


def classify_exception(e: BaseException) -> tuple[str, str]:
    """异常 → (错误码, 面向用户的文案)。

    🔴 **绝不把原始异常文本透给前端**：里面可能含内网 URL、Redis 连接串、
    文件路径、栈帧片段——既是信息泄露，用户也看不懂。原文只进日志
    （调用方用 logger.exception 记全量）。
    """
    names = {c.__name__ for c in type(e).__mro__}
    for cls_name, mapped in _ERROR_MAP.items():
        if cls_name in names:
            return mapped
    # 工具层把商城接口的网络/HTTP 错误包成了 ToolException
    if "ToolException" in names:
        return "mall_unavailable", "商城服务暂时不可用，请稍后再试"
    if "RedisError" in names or "ConnectionError" in names or "TimeoutError" in names:
        return "state_unavailable", "服务状态异常，请稍后再试"
    return "internal", "服务出了点问题，请稍后再试"


# ---------------------------------------------------------------- token 计量

class TokenUsageCollector(BaseCallbackHandler):
    """累计**一轮请求内**所有 LLM 调用的 token 用量。

    ⚠️ 为什么不能用「最后一条消息的 usage」：agent 一轮里可能调 N 次 LLM
    （每次工具调用前后各一次），只看末次会**严重低估**成本——恰恰在
    「工具调用最多、也就是最贵」的场景下错得最离谱。

    必须真继承 `BaseCallbackHandler`：LangChain 的 callback 管理器虽然是按方法名
    鸭子调用，但只有继承了才会被正常注册与传播（`run_inline` / `raise_error`
    等属性也来自基类）。依赖确实变重了，但**统计静默失效 = 成本上限形同虚设**，
    这个代价不能省。
    """

    def __init__(self) -> None:
        self.calls = 0
        self.total = 0

    def on_llm_end(self, response, **kwargs) -> None:  # noqa: ANN001
        try:
            self.calls += 1
            self.total += _extract_tokens(response)
        except Exception:  # noqa: BLE001 —— 计量失败绝不该影响对话
            pass


def _extract_tokens(response) -> int:
    """从 LLMResult 挖 total_tokens：优先新式 usage_metadata，回退 llm_output。"""
    for row in (getattr(response, "generations", None) or []):
        for g in (row if isinstance(row, (list, tuple)) else [row]):
            md = getattr(getattr(g, "message", None), "usage_metadata", None)
            if isinstance(md, dict) and md.get("total_tokens"):
                return int(md["total_tokens"])
    out = getattr(response, "llm_output", None) or {}
    usage = out.get("token_usage") or out.get("usage") or {}
    if isinstance(usage, dict):
        for k in ("total_tokens", "total"):
            if usage.get(k):
                return int(usage[k])
    return 0


def record_usage(n: int) -> int:
    """把本轮 token 累加进全站当日用量。失败静默——统计不该影响对话。"""
    try:
        return store.add_tokens(n)
    except redis.RedisError as e:
        logger.warning("token 用量写入失败（忽略）：%s", e)
        return 0


# ---------------------------------------------------------------- 诊断

def status() -> dict:
    """当前治理配置（`--check` 类脚本与验收用）。"""
    return {
        "enabled": config.GUARD_ENABLED,
        "ratePerMinMember": config.RATE_PER_MIN_MEMBER,
        "ratePerMinGuest": config.RATE_PER_MIN_GUEST,
        "quotaPerDayMember": config.QUOTA_PER_DAY_MEMBER,
        "quotaPerDayGuest": config.QUOTA_PER_DAY_GUEST,
        "dailyTokenLimit": config.DAILY_TOKEN_LIMIT,
        "fallbackModel": config.DEEPSEEK_FALLBACK_MODEL or "（未配置 → 超预算即停）",
        "llmTimeout": config.LLM_TIMEOUT,
        "llmMaxRetries": config.LLM_MAX_RETRIES,
    }
