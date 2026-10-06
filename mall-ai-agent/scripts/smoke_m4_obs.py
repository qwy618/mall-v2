"""M4.3 可观测性验收：traceId 贯穿 / 结构化 JSON 日志 / 核心指标。

**不依赖 LLM**。A 组（trace）与 B 组（日志）纯进程内；C/D 组需要 Redis
（指标聚合走 Redis Hash），Redis 不可用时自动 SKIP 而不是 FAIL —— 本机没起
Redis 时也应该能验证"日志与追踪"这半边。

覆盖：
  A trace.py：id 生成 / 外部值白名单（防日志注入）/ contextvar 存取 / 中间件透传与回写
  B JsonFormatter：输出合法 JSON、字段齐全、**凭据在该 JSON 里被脱敏且 JSON 仍合法**（关键回归）
  C metrics：标签编码稳定 / record_turn 落库 / 分桶与 P95 / snapshot 派生比率 / 拒答分类 / 工具回调
  D 端点：/api/metrics 正常 200、开关关闭 404、配了令牌则 403/200；治理拦截会被记账

运行：
    .venv\\Scripts\\python scripts/smoke_m4_obs.py
"""
from __future__ import annotations

import io
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config, logmask, metrics, store, trace        # noqa: E402

PASS = 0
FAIL = 0
SKIP = 0
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


def skip(name: str, why: str) -> None:
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {name}   ── {why}")


def group(title: str) -> None:
    print(f"\n=== {title} ===")


# ================================================================ A. trace
group("A. trace.py —— traceId 生成 / 白名单 / contextvar / 中间件")

tid = trace.new_id()
check("A1 new_id() 是 12 位 hex", len(tid) == 12 and all(c in "0123456789abcdef" for c in tid), tid)
check("A2 两次生成不重复", trace.new_id() != tid)

check("A3 sanitize 放行合法值", trace.sanitize("abc-123_XYZ.9") == "abc-123_XYZ.9")
check("A4 sanitize 去掉两端空白", trace.sanitize("  t-1  ") == "t-1")
# 日志注入防线：这些若被放行，会伪造日志行 / 撑破 JSON
for bad, why in [("a\nb", "含换行"), ('a"b', "含引号"), ("x" * 65, "超长"),
                 ("中文", "非 ASCII"), ("a b", "含空格"), ("", "空串")]:
    check(f"A5 sanitize 拒绝非法值（{why}）", trace.sanitize(bad) == "", repr(bad)[:30])

tok = trace.set_trace("T-outer")
check("A6 set_trace 后 get_trace 返回该值", trace.get_trace() == "T-outer")
trace.set_trace(None)
check("A6b set_trace(None) 自动补发新 id",
      len(trace.get_trace()) == 12 and trace.sanitize(trace.get_trace()) == trace.get_trace(),
      trace.get_trace())
trace.reset(tok)
check("A7 reset 后恢复外层值", trace.get_trace() == "")

stok = trace.set_session("sess-1")
check("A8 session contextvar 可读写", trace.get_session() == "sess-1")
trace.reset_session(stok)
check("A8b session reset 后为空", trace.get_session() == "")

from fastapi.testclient import TestClient                        # noqa: E402

from app.main import app                                         # noqa: E402

client = TestClient(app)
r = client.get("/health", headers={"X-Trace-Id": "trace-from-upstream"})
check("A9 上游传入的 traceId 被原样回写响应头",
      r.headers.get("x-trace-id") == "trace-from-upstream",
      f"header={r.headers.get('x-trace-id')!r}")

r = client.get("/health")
got = r.headers.get("x-trace-id", "")
check("A10 未传时服务自己生成（响应头非空且合法）",
      len(got) == 12 and trace.sanitize(got) == got, f"header={got!r}")

r = client.get("/health", headers={"X-Trace-Id": "bad id!!"})
got = r.headers.get("x-trace-id", "")
check("A11 非法 traceId 被丢弃、改为服务生成（防日志注入）",
      got != "bad id!!" and trace.sanitize(got) == got, f"header={got!r}")


# ================================================================ B. JSON 日志
group("B. JsonFormatter —— 结构化输出 + 逐字段脱敏（JSON 仍合法）")

JWT = ("eyJhbGciOiJIUzUxMiJ9."
       "eyJzdWIiOiIxMzkwMDAwNzc3NyIsImV4cCI6MTc5OTk5OTk5OX0."
       "abcdefghijklmnopqrstuvwxyz0123456789")

buf = io.StringIO()
lh = logging.getLogger("smoke.m4.obs")
lh.handlers.clear()
lh.propagate = False
sh = logging.StreamHandler(buf)
sh.setFormatter(logmask.JsonFormatter())
lh.addHandler(sh)
lh.setLevel(logging.DEBUG)


def last_json() -> dict:
    lines = [ln for ln in buf.getvalue().strip().splitlines() if ln.strip()]
    return json.loads(lines[-1])


trace.set_trace("T-json")
trace.set_session("sess-json")
lh.info("turn end surface=sse outcome=ok dur=%.0fms", 12.0,
        extra={"surface": "sse", "outcome": "ok", "durationMs": 12, "tools": "a:1/0"})
obj = last_json()
check("B1 输出是合法 JSON", isinstance(obj, dict), str(obj)[:120])
check("B2 固定字段齐全（ts/level/logger/msg/traceId/sessionId）",
      all(k in obj for k in ("ts", "level", "logger", "msg", "traceId", "sessionId")),
      str(sorted(obj.keys())))
check("B3 traceId 来自 contextvar", obj.get("traceId") == "T-json", obj.get("traceId"))
check("B4 sessionId 来自 contextvar", obj.get("sessionId") == "sess-json", obj.get("sessionId"))
check("B5 extra 字段成为可检索字段",
      obj.get("tools") == "a:1/0" and obj.get("durationMs") == 12, str(obj))

# 🔴 关键回归：脱敏不能破坏 JSON 结构
buf.truncate(0)
buf.seek(0)
lh.info('回调参数 token=%s 与 JSON 里的 password', JWT)
lh.info('{"username":"amy","password":"p@ssw0rd!"}')
lh.info("Bearer %s", JWT)
raw = buf.getvalue().strip().splitlines()
ok_json = True
for ln in raw:
    try:
        json.loads(ln)
    except json.JSONDecodeError:
        ok_json = False
check("B6 含凭据的日志行仍是合法 JSON（逐字段脱敏，不对整行 mask）", ok_json,
      raw[-1][:160] if raw else "")
check("B7 凭据原文在 JSON 输出里已消失",
      all(JWT not in ln and "p@ssw0rd!" not in ln for ln in raw))
check("B8 脱敏标记出现在 JSON 里",
      any(logmask.MASK in ln for ln in raw), raw[0][:160])

# 异常堆栈同样要脱敏，且仍合法 JSON
buf.truncate(0)
buf.seek(0)
try:
    raise RuntimeError(f"httpx 失败 url=http://10.0.0.5/info?token={JWT}")
except RuntimeError:
    lh.exception("流式对话失败")
obj = last_json()
check("B9 异常堆栈脱敏后仍合法 JSON", isinstance(obj.get("exc"), str), str(obj)[:80])
check("B10 堆栈里的 token 原文已消失", JWT not in json.dumps(obj, ensure_ascii=False))
check("B11 堆栈仍保留异常类型（可排查）", "RuntimeError" in obj.get("exc", ""))

# 文本模式：也要带 trace 前缀（否则文本日志里 traceId 形同虚设）
tbuf = io.StringIO()
th = logging.StreamHandler(tbuf)
th.setFormatter(logmask.MaskingFormatter(
    "%(levelname)s [t=%(trace_id)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
lh.handlers = [th]
lh.info("hello")
check("B12 文本 formatter 输出带 trace_id", "[t=T-json]" in tbuf.getvalue(),
      tbuf.getvalue().strip())

lh.handlers = [sh]           # 还原，不干扰后续
trace.set_session("")        # 清掉，避免污染其他组


# ================================================================ C. 指标
group("C. metrics —— 标签编码 / 落库 / 分桶 P95 / 派生比率 / 工具回调")

try:
    store.assert_available()
    redis_ok = True
except Exception as e:  # noqa: BLE001
    redis_ok = False
    print(f"  （Redis 不可用：{e}）")

if not redis_ok:
    for n in ["C1 标签编码稳定", "C2 record_turn 落库", "C3 延迟分桶与 P95",
              "C4 snapshot 派生", "C5 拒答分类", "C6 工具回调"]:
        skip(n, "Redis 不可用")
else:
    DAY = "20990101"                       # 隔离日：不污染当天真实指标
    store.metric_clear(DAY)

    check("C1 标签编码稳定（顺序不同 → 同一 field）",
          metrics._field("tool", {"b": "2", "a": "1"})
          == metrics._field("tool", {"a": "1", "b": "2"})
          == "tool|a=1,b=2", metrics._field("tool", {"b": "2", "a": "1"}))

    metrics.record_turn("sse", "ok", 1200,
                        tools={"search_products": {"ok": 2, "err": 1}}, day=DAY)
    metrics.record_turn("sse", "ok", 300, answer="这款手机口碑不错", day=DAY)
    metrics.record_turn("http", "blocked", 5, day=DAY)
    metrics.record_turn("http", "error", 8000, day=DAY)
    counters, latency = store.metric_dump(DAY)

    check("C2 record_turn 落库（req/tool/answer 计数）",
          counters.get("req|outcome=ok,surface=sse") == 2
          and counters.get("req|outcome=blocked,surface=http") == 1
          and counters.get("tool|result=ok,tool=search_products") == 2
          and counters.get("tool|result=err,tool=search_products") == 1
          and counters.get("answer|kind=normal") == 1,
          str(counters))
    check("C3 延迟分桶与 sum/count",
          latency.get("count") == 4 and latency.get("sum") == 1200 + 300 + 5 + 8000
          and latency.get("le_500") == 2 and latency.get("le_2000") == 1
          and latency.get("le_10000") == 1,
          str(latency))

    snap = metrics.snapshot(day=DAY)
    d = snap["derived"]
    # 比率在 snapshot 里按 4 位小数取整，断言跟 round(...,4) 比，别死磕浮点尾数
    check("C4 snapshot 派生比率正确",
          d["requestsTotal"] == 4
          and d["toolSuccessRate"] == round(2 / 3, 4)
          and d["errorRate"] == 0.25
          and d["blockedRate"] == 0.25,
          json.dumps(d, ensure_ascii=False))
    check("C4b snapshot 含 p95 / 延迟均值",
          snap["latency"]["p95Ms"] is not None and snap["latency"]["avgMs"] > 0,
          json.dumps(snap["latency"], ensure_ascii=False))

    # P95 纯函数：10 个样本，5 个 <=500ms、5 个 <=1000ms → 第 95 百分位落在 1000ms 桶
    p = metrics.percentile({"le_500": 5, "le_1000": 5}, 10, 0.95)
    check("C4c percentile 取累积占比首次 ≥q 的桶上界", p == 1000.0, str(p))
    check("C4d percentile 空集返回 None", metrics.percentile({}, 0, 0.95) is None)

    check("C5 拒答分类：话术命中 → refusal",
          metrics.classify_answer("抱歉，我这边没有找到相关信息") == "refusal")
    check("C5b 拒答分类：正常回答 → normal",
          metrics.classify_answer("这款手机续航不错，适合学生") == "normal")

    cb = metrics.ToolUsageCollector()
    cb.on_tool_start({"name": "search_products"}, "", run_id="r1")
    cb.on_tool_start({"name": "search_products"}, "", run_id="r2")
    cb.on_tool_end(object(), run_id="r1")
    cb.on_tool_error(RuntimeError("boom"), run_id="r2")
    cb.on_tool_start({"name": "show_products"}, "", run_id="r3")
    cb.on_tool_end(object(), run_id="r3")
    check("C6 工具回调按工具名统计成功/失败",
          cb.summary() == {"search_products": {"ok": 1, "err": 1},
                           "show_products": {"ok": 1, "err": 0}}, str(cb.summary()))
    check("C6b describe() 一行摘要", cb.describe() == "search_products:1/1,show_products:1/0",
          cb.describe())

    store.metric_clear(DAY)
    check("C7 测试日指标已清理（不污染真实数据）", store.metric_dump(DAY) == ({}, {}))


# ================================================================ D. 端点
group("D. /api/metrics 与「拦截也记账」")

if not redis_ok:
    skip("D1 metrics 端点", "Redis 不可用")
else:
    r = client.get("/api/metrics")
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    check("D1 GET /api/metrics 返回 200 且含四类内容",
          r.status_code == 200
          and all(k in body for k in ("day", "latency", "counters", "derived", "tokensToday")),
          f"status={r.status_code} keys={sorted(body.keys())}")

    # 开关关闭 → 404
    old_enabled, old_token = config.METRICS_ENABLED, config.METRICS_TOKEN
    config.METRICS_ENABLED = False
    check("D2 METRICS_ENABLED=0 时 404", client.get("/api/metrics").status_code == 404)
    config.METRICS_ENABLED = True
    config.METRICS_TOKEN = "s3cr3t-metrics"
    check("D3 配了令牌后无令牌 → 403", client.get("/api/metrics").status_code == 403)
    check("D3b 带 query 令牌 → 200",
          client.get("/api/metrics?token=s3cr3t-metrics").status_code == 200)
    check("D3c 带 header 令牌 → 200",
          client.get("/api/metrics",
                     headers={"X-Metrics-Token": "s3cr3t-metrics"}).status_code == 200)
    config.METRICS_TOKEN = old_token
    config.METRICS_ENABLED = old_enabled

    # 治理拦截路径必须记账（用当天真实键，比对增量而不是绝对值）
    old_rate = config.RATE_PER_MIN_GUEST
    try:
        before = store.metric_dump()[0].get("req|outcome=blocked,surface=http", 0)
        config.RATE_PER_MIN_GUEST = 0            # 游客第 1 次就超限 → 必然被拦
        r = client.post("/api/chat", json={"message": "hi", "session_id": "smoke-m43"})
        after = store.metric_dump()[0].get("req|outcome=blocked,surface=http", 0)
        check("D4 治理拦截被计入指标（blocked +1）且响应 429",
              r.status_code == 429 and after - before == 1,
              f"status={r.status_code} delta={after - before}")
    finally:
        config.RATE_PER_MIN_GUEST = old_rate
        # 刻意**不**清理当天指标：那会把用户当天真实数据一起抹掉。
        # 代价只是本脚本给当天加了 1 条 blocked 计数与 1 个延迟样本，可忽略。
        # （真正的「清空」只用于隔离日 DAY，见 C 组。）

check("D5 日志配置 status() 可读且含 format 字段",
      "format" in logmask.status() and "bucketsMs" in metrics.status(),
      str(logmask.status()))


# ================================================================ 收尾
print(f"\n{'=' * 56}")
print(f"合计 {PASS + FAIL + SKIP} 项：PASS {PASS} / FAIL {FAIL} / SKIP {SKIP}")
if FAILED:
    print("失败项：")
    for n in FAILED:
        print(f"  · {n}")
print("=" * 56)
sys.exit(1 if FAIL else 0)
