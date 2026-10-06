"""M4.1 治理层验收：限流 / 配额 / 成本上限 / 异常友好化。

**不依赖 LLM、不依赖 HTTP** —— 纯 store 计数原语 + guard 纯函数，毫秒级、可重复运行。

不污染真实数据：计数键统一用 `smk{pid}{ts}` 前缀，测试 IP 用 RFC5737 文档网段
（198.51.x.x，不会是真实机器）。唯一碰真实键的是「全站 token 累计」那组，
它在 finally 里按原值减回并核对。

运行：
    .venv\\Scripts\\python scripts/smoke_m4_guard.py
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import redis                                              # noqa: E402

from app import config, guard, store                      # noqa: E402

TAG = f"smk{os.getpid()}{int(time.time()) % 100000}"
TEST_NET = "198.51"          # RFC5737 文档用网段

PASS = 0
FAIL = 0
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        FAILED.append(name)
        print(f"  [FAIL] {name}" + (f"   ── {detail}" if detail else ""))


def group(title: str) -> None:
    print(f"\n=== {title} ===")


@contextmanager
def temp_config(**kw):
    """临时改配置，退出时还原（测试阈值用，避免动真实配置）。"""
    old = {k: getattr(config, k) for k in kw}
    for k, v in kw.items():
        setattr(config, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(config, k, v)


def cleanup() -> int:
    n = 0
    for pat in (f"ai:rate:{TAG}*", f"ai:quota:{TAG}*",
                f"ai:rate:ip{TEST_NET}.*", f"ai:quota:ip{TEST_NET}.*",
                "ai:rate:iptestclient*", "ai:quota:iptestclient*"):
        for k in store.client().scan_iter(pat):
            store.client().delete(k)
            n += 1
    return n


# ---------------------------------------------------------------- A. 身份

group("A. 身份解析")
sub_m, is_m = guard.subject_of("1.2.3.4", 77)
check("会员按 memberId 计数（不受 IP 变化影响）", sub_m == "m77" and is_m, sub_m)
sub_g, is_g = guard.subject_of("1.2.3.4", None)
check("游客按 IP 计数", sub_g == "ip1.2.3.4" and not is_g, sub_g)
check("游客身份不含 session 概念（换 session_id 无法绕过）", "session" not in sub_g)
check("ip_of 对非 Request 对象容错（验收脚本要能直接调）",
      guard.ip_of(None) == "unknown")
check("两种身份在 Redis 中不撞键", sub_m != sub_g)

# ---------------------------------------------------------------- B. 计数原语

group("B. 计数原语（Redis + Lua）")
rl = f"{TAG}r"
n1, n2, n3 = store.hit_rate(rl), store.hit_rate(rl), store.hit_rate(rl)
check("限流计数单调递增", (n1, n2, n3) == (1, 2, 3), f"{n1},{n2},{n3}")
check("peek_rate 只读不递增", store.peek_rate(rl) == 3)

bucket = time.strftime("%Y%m%d%H%M")
rk = f"ai:rate:{rl}:{bucket}"
check("键名按分钟分桶 → 跨分钟自动换 key、无需清理任务",
      store.client().exists(rk) == 1)
ttl1 = store.client().ttl(rk)
check("键带 TTL（不会永久计数把用户限死）", 0 < ttl1 <= 90, f"ttl={ttl1}")

time.sleep(1.2)
store.hit_rate(rl)
ttl2 = store.client().ttl(rk)
check("再次计数**不续期** TTL（否则退化成滑动窗口，可无限续期永不被限）",
      ttl2 <= ttl1, f"{ttl1} → {ttl2}")

q = f"{TAG}q"
check("配额计数递增", (store.hit_quota(q), store.hit_quota(q)) == (1, 2))
check("peek_quota 只读不递增", store.peek_quota(q) == 2)

# ---------------------------------------------------------------- C. 门禁

group("C. 门禁：限流拦截")
ip_rate = f"{TEST_NET}.10.1"
with temp_config(RATE_PER_MIN_GUEST=3, QUOTA_PER_DAY_GUEST=1000,
                 DAILY_TOKEN_LIMIT=10 ** 9):
    ok3 = [guard.check(ip_rate, None) for _ in range(3)]
    blocked = guard.check(ip_rate, None)
check("阈值内放行", all(d.allowed for d in ok3))
check("超阈值被拦", not blocked.allowed)
check("code=rate_limited（前端可据此做差异化 UI）",
      blocked.code == "rate_limited", blocked.code)
check("文案指向「稍等」而非「明天」",
      "稍等" in blocked.message and "明天" not in blocked.message, blocked.message)
check("决策带回当前计数（可观测）", blocked.rate == 4, f"rate={blocked.rate}")

group("C2. 门禁：配额拦截")
ip_quota = f"{TEST_NET}.20.1"
with temp_config(RATE_PER_MIN_GUEST=1000, QUOTA_PER_DAY_GUEST=2,
                 DAILY_TOKEN_LIMIT=10 ** 9):
    ok2 = [guard.check(ip_quota, None) for _ in range(2)]
    q_blocked = guard.check(ip_quota, None)
check("阈值内放行", all(d.allowed for d in ok2))
check("超配额被拦", not q_blocked.allowed)
check("code=quota_exceeded", q_blocked.code == "quota_exceeded", q_blocked.code)
check("文案指向「明天再来」（与限流明确区分）", "明天" in q_blocked.message,
      q_blocked.message)

ip_mix = f"{TEST_NET}.20.2"
with temp_config(RATE_PER_MIN_GUEST=1, QUOTA_PER_DAY_GUEST=1000,
                 DAILY_TOKEN_LIMIT=10 ** 9):
    guard.check(ip_mix, None)
    guard.check(ip_mix, None)      # 第 2 次会被限流拦下
check("被限流的请求不消耗日配额（先限流后配额，挡住的不算数）",
      store.peek_quota(f"ip{ip_mix}") == 1, f"quota={store.peek_quota(f'ip{ip_mix}')}")

group("C3. 一键回退开关")
ip_off = f"{TEST_NET}.25.1"
with temp_config(GUARD_ENABLED=False, RATE_PER_MIN_GUEST=0):
    d_off = guard.check(ip_off, None)
check("GUARD_ENABLED=0 时完全跳过治理（排查误伤用）", d_off.allowed)

# ---------------------------------------------------------------- D. 成本上限

group("D. 成本上限与降级")
with temp_config(RATE_PER_MIN_GUEST=1000, QUOTA_PER_DAY_GUEST=1000,
                 DAILY_TOKEN_LIMIT=0, DEEPSEEK_FALLBACK_MODEL=""):
    d_stop = guard.check(f"{TEST_NET}.30.1", None)
check("超预算且无 fallback → 停止对话", not d_stop.allowed)
check("code=budget_exhausted", d_stop.code == "budget_exhausted", d_stop.code)

with temp_config(RATE_PER_MIN_GUEST=1000, QUOTA_PER_DAY_GUEST=1000,
                 DAILY_TOKEN_LIMIT=0, DEEPSEEK_FALLBACK_MODEL="deepseek-chat-lite"):
    d_deg = guard.check(f"{TEST_NET}.30.2", None)
check("超预算且有 fallback → 放行并标记降级（降级而非中断）",
      d_deg.allowed and d_deg.degraded)

with temp_config(RATE_PER_MIN_GUEST=1000, QUOTA_PER_DAY_GUEST=1000,
                 DAILY_TOKEN_LIMIT=10 ** 9, DEEPSEEK_FALLBACK_MODEL="x"):
    d_norm = guard.check(f"{TEST_NET}.30.3", None)
check("预算充足时不标记降级", d_norm.allowed and not d_norm.degraded)

# ---------------------------------------------------------------- E. 异常分类

group("E. 异常友好化")


def make_exc(name: str, msg: str = "") -> BaseException:
    return type(name, (Exception,), {})(msg)


for cls_name, want in [
    ("APITimeoutError", "llm_timeout"),
    ("RateLimitError", "llm_busy"),
    ("APIConnectionError", "llm_unreachable"),
    ("AuthenticationError", "llm_auth"),
    ("ToolException", "mall_unavailable"),
    ("RedisError", "state_unavailable"),
    ("SomeUnknownExplosion", "internal"),
]:
    got, _ = guard.classify_exception(make_exc(cls_name))
    check(f"{cls_name} → {want}", got == want, f"got={got}")

secret = "连接 redis://:p@ssw0rd@10.0.0.5:6379/0 失败；file=/srv/app/secret.py"
code_s, msg_s = guard.classify_exception(make_exc("RedisError", secret))
check("🔴 用户文案不含原始异常文本（防泄露连接串/内网 IP/路径）",
      "p@ssw0rd" not in msg_s and "10.0.0.5" not in msg_s and "/srv/app" not in msg_s,
      msg_s)
check("但错误码仍可用于日志检索定位", code_s == "state_unavailable")
check("文案是中文且面向用户（不含英文异常名）",
      not any(x in msg_s for x in ("Error", "Exception", "Traceback")), msg_s)

# ---------------------------------------------------------------- F. fail-open

group("F. fail-open（治理故障不阻断业务）")
orig_hit_rate = store.hit_rate


def _boom(*a, **k):
    raise redis.RedisError("模拟 Redis 抖动")


store.hit_rate = _boom
try:
    d_fo = guard.check(f"{TEST_NET}.40.1", None)
finally:
    store.hit_rate = orig_hit_rate
check("计数失败时放行（治理是控制面，不该成为新的单点故障）", d_fo.allowed)
check("fail-open 时不误标降级", not d_fo.degraded)

# ---------------------------------------------------------------- G. token 计量

group("G. token 计量（一轮内多次 LLM 调用要累加）")


class _Msg:
    def __init__(self, n): self.usage_metadata = {"total_tokens": n}


class _Gen:
    def __init__(self, n): self.message = _Msg(n)


class _Res:
    def __init__(self, gens, llm_output=None):
        self.generations = gens
        self.llm_output = llm_output


c = guard.TokenUsageCollector()
c.on_llm_end(_Res([[_Gen(10)]]))
c.on_llm_end(_Res([[_Gen(25)]]))
check("累计同一轮内的多次 LLM 调用（只看末次会严重低估成本）",
      c.total == 35, f"total={c.total}")
check("调用次数也被记录", c.calls == 2)
check("回退读 llm_output.token_usage（旧版 SDK 形态）",
      guard._extract_tokens(_Res([], {"token_usage": {"total_tokens": 7}})) == 7)
c.on_llm_end(object())
check("对畸形响应容错（计量失败绝不影响对话）", c.total == 35)

# ---------------------------------------------------------------- H. 真实写入

group("H. 全站 token 累计（真实键，跑完还原）")
token_key = f"ai:token:day:{time.strftime('%Y%m%d')}"
before = store.peek_tokens()
delta = 4321
try:
    after = store.add_tokens(delta)
    check("add_tokens 递增", after == before + delta, f"{before} → {after}")
    check("add_tokens(0) 只读不写", store.add_tokens(0) == after)
    check("累加不重置 TTL（多轮累加不会把窗口往后推）",
          store.client().ttl(token_key) > 0)
finally:
    store.client().decrby(token_key, delta)
    if store.client().get(token_key) in (None, "0"):
        store.client().delete(token_key)
check("跑完已还原全站计数（不污染真实用量）",
      store.peek_tokens() == before, f"{store.peek_tokens()} vs {before}")

# ---------------------------------------------------------------- I. HTTP 端到端

group("I. HTTP 端到端拦截（TestClient，被拦的请求不该花钱）")
try:
    from fastapi.testclient import TestClient            # noqa: PLC0415

    from app.main import app                             # noqa: PLC0415

    client = TestClient(app)
    with temp_config(RATE_PER_MIN_GUEST=0, QUOTA_PER_DAY_GUEST=1000,
                     DAILY_TOKEN_LIMIT=10 ** 9):
        resp = client.post("/api/chat/stream", json={"message": "你好"})
    body = resp.text
    check("HTTP 状态码 200（SSE 用事件而非状态码表达业务拒绝）",
          resp.status_code == 200, str(resp.status_code))
    check("响应体含 error 事件", "error" in body)
    check("携带 code=rate_limited（前端据此做差异化 UI）", "rate_limited" in body)
    check("🔴 被拦的请求未触发 LLM（零 token 成本）",
          "event: token" not in body and '"type": "token"' not in body)

    # 注意：这里**只验证拦截路径**。放行路径一旦通过门禁就会真的调 LLM
    # （花 token、依赖 portal 与 DeepSeek 在线），会让本脚本失去「零成本、可重复」
    # 的定位。放行决策本身已由 C 组覆盖；完整链路另用真实服务验证。
except Exception as e:  # noqa: BLE001
    check("HTTP 端到端验证可执行", False, f"{type(e).__name__}: {e}")

# ---------------------------------------------------------------- 收尾

print(f"\n{'=' * 48}")
print(f"结果：{PASS}/{PASS + FAIL} 通过")
if FAILED:
    print("失败项：")
    for f in FAILED:
        print(f"  · {f}")
print(f"已清理测试键 {cleanup()} 个")
sys.exit(1 if FAIL else 0)
