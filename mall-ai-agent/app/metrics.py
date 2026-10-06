"""核心指标（M4.3）：工具成功率 / 拒答率 / 订单转化 / 延迟分布。

## 为什么指标也放 Redis

和 guard 的计数同一条理由：进程内 Counter 在多 worker 下**每个 worker 各算一份**，
`--workers 4` 时 `GET /api/metrics` 只反映命中当前 worker 的流量，数字随机且偏小。
放 Redis Hash 后：写是一把 `HINCRBY`，读是一把 `HGETALL`，跨 worker 天然聚合。

## 延迟为什么用分桶直方图，不存原始样本

Redis 没有「取第 95 百分位」这种原语，存几万个原始样本再取分位数既费内存又慢。
分桶计数体积恒定（桶数固定）、可跨 worker 累加，P95 取「累积占比首次 ≥95% 的桶上界」。
代价是**偏保守**（P95 会被算成某个更粗的上界）——对「看延迟是否退化」这个用途足够，
要精确分位数就上 Prometheus/Langfuse（M4.5），那是它们的主场。

🔴 所有写入一律 fail-open：统计失败绝不能拖垮对话，与 guard 同一条原则。
"""
from __future__ import annotations

import logging

from langchain_core.callbacks import BaseCallbackHandler

from . import store

logger = logging.getLogger(__name__)

# 延迟桶上界（毫秒）。覆盖「快问快答 ~1s」到「多次工具调用 ~30s」的常见区间。
# 定义在 store.py（写侧），这里引用同一份，避免读写两侧桶边界漂移。
LATENCY_BUCKETS_MS = store.LATENCY_BUCKETS_MS

# 拒答话术表。与 scripts/eval_golden.py 共用同一份定义（那边 import 这里），
# 避免「金标集认定是拒答、生产指标却不认」这种两套口径的问题。
REFUSAL_HINTS = [
    "没有找到", "没有相关", "暂无相关", "无法回答", "不太了解", "不太清楚",
    "帮不上", "没有足够", "查不到", "查不了", "无法查", "暂时没有",
    "我这边没有", "无法提供", "没有这方面", "不清楚", "抱歉", "不好意思",
]


def _field(name: str, labels: dict) -> str:
    """把 (指标名, 标签) 编码成一个 Hash field。

    形如 `tool|result=ok,tool=search_products`。标签**必须排序**再拼，
    否则 `tool+result` 与 `result+tool` 会变成两个 field，同一件事被拆成两行。
    """
    if not labels:
        return name
    return name + "|" + ",".join(f"{k}={v}" for k, v in sorted(labels.items()))


def _parse_field(field: str) -> tuple[str, dict]:
    name, _, rest = field.partition("|")
    labels: dict[str, str] = {}
    for kv in filter(None, rest.split(",")):
        k, _, v = kv.partition("=")
        labels[k] = v
    return name, labels


def incr(name: str, count: int = 1, day: str | None = None, **labels) -> None:
    """给某个 (指标, 标签) 计数。失败静默。day 仅验收脚本隔离用。"""
    if count:
        _safe(lambda: store.metric_incr_many({_field(name, labels): int(count)}, day))


def observe_latency(ms: float, day: str | None = None) -> None:
    _safe(lambda: store.metric_latency(ms, day))


def classify_answer(text: str) -> str:
    """把一轮回复粗分成 normal / refusal。

    ⚠️ 这是**基于话术关键词的启发式**，只用于「大概看着有没有异常」的看板。
    要精确评估拒答/幻觉得上金标集（M3.5 已有）——别拿这个数字下结论。
    """
    t = text or ""
    for h in REFUSAL_HINTS:
        if h in t:
            return "refusal"
    return "normal"


def _safe(fn) -> None:
    try:
        fn()
    except Exception as e:  # noqa: BLE001 —— 统计不该影响业务
        logger.warning("指标写入失败（忽略）：%s", e)


def record_turn(surface: str, outcome: str, duration_ms: float,
                tools: dict | None = None, answer: str | None = None,
                extra: dict | None = None, day: str | None = None) -> None:
    """一轮对话收尾时**一次**写好本次全部指标（单次 Redis 往返）。

    surface: http | sse       —— 走的是非流式还是流式入口
    outcome: ok | error | blocked | need_login | empty
    tools:   {tool_name: {"ok": n, "err": m}}（由 ToolUsageCollector 汇总）
    answer:  本轮正文（用于粗分拒答率）
    """
    counters: dict[str, int] = {
        _field("req", {"surface": surface, "outcome": outcome}): 1,
    }
    for tool, st in (tools or {}).items():
        ok, err = int(st.get("ok", 0)), int(st.get("err", 0))
        if ok:
            counters[_field("tool", {"result": "ok", "tool": tool})] = ok
        if err:
            counters[_field("tool", {"result": "err", "tool": tool})] = err
    if answer is not None:
        counters[_field("answer", {"kind": classify_answer(answer)})] = 1
    for k, v in (extra or {}).items():
        if v:
            counters[_field(k, {})] = int(v)
    _safe(lambda: store.metric_incr_many(counters, day))
    observe_latency(duration_ms, day)


class ToolUsageCollector(BaseCallbackHandler):
    """按工具名统计本轮成功 / 失败次数。

    为什么必须在回调里数，而不能在主流程里数：工具内部抛的异常会被 LangChain
    捕获、包成 `ToolException` 再作为 tool 消息回给模型 —— **它不会冒泡到最外层**，
    所以 main 的 `try/except` 根本看不到「某个工具失败了」。只有 `on_tool_error`
    这个回调能拿到。

    ⚠️ `on_tool_end` / `on_tool_error` **只给 run_id、不给工具名**，名字只出现在
    `on_tool_start` 的 `serialized` 里 → 必须自己维护 run_id → name 的映射。
    """

    def __init__(self) -> None:
        self._names: dict[str, str] = {}
        self._stats: dict[str, dict[str, int]] = {}

    def _bump(self, name: str, key: str) -> None:
        row = self._stats.setdefault(name, {"ok": 0, "err": 0})
        row[key] = row.get(key, 0) + 1

    def _name_of(self, run_id) -> str:
        return self._names.get(str(run_id), "unknown") if run_id is not None else "unknown"

    def on_tool_start(self, serialized, input_str, **kwargs) -> None:  # noqa: ANN001
        try:
            name = (serialized or {}).get("name") or "unknown"
            run_id = kwargs.get("run_id")
            if run_id is not None:
                self._names[str(run_id)] = name
        except Exception:  # noqa: BLE001 —— 统计失败绝不影响对话
            pass

    def on_tool_end(self, output, **kwargs) -> None:  # noqa: ANN001
        try:
            self._bump(self._name_of(kwargs.get("run_id")), "ok")
        except Exception:  # noqa: BLE001
            pass

    def on_tool_error(self, error, **kwargs) -> None:  # noqa: ANN001
        try:
            self._bump(self._name_of(kwargs.get("run_id")), "err")
        except Exception:  # noqa: BLE001
            pass

    def summary(self) -> dict:
        """{工具名: {"ok": n, "err": m}}，供写指标用。"""
        return {k: dict(v) for k, v in sorted(self._stats.items())}

    def describe(self) -> str:
        """一行摘要，给日志用：`search_products:2/0,show_products:1/0`。"""
        if not self._stats:
            return "-"
        return ",".join(f"{k}:{v.get('ok', 0)}/{v.get('err', 0)}"
                        for k, v in sorted(self._stats.items()))


# ---------------------------------------------------------------- 读侧

def _sum_where(counters: dict[str, int], name: str, **want) -> int:
    """按 (指标名 + 部分标签匹配) 求和。"""
    total = 0
    for field, n in counters.items():
        fname, labels = _parse_field(field)
        if fname != name:
            continue
        if all(labels.get(k) == v for k, v in want.items()):
            total += n
    return total


def _ratio(a: int, b: int) -> float:
    return round(a / b, 4) if b else 0.0


def percentile(buckets: dict[str, int], total: int, q: float) -> float | None:
    """从分桶计数估百分位：返回累积占比首次 ≥ q 的桶上界（ms）。

    空集合返回 None；超过最大桶则返回最大桶（说明尾部很长，需要人工看）。
    """
    if total <= 0:
        return None
    target = total * q
    acc = 0
    for upper in LATENCY_BUCKETS_MS:
        acc += int(buckets.get(f"le_{upper}", 0))
        if acc >= target:
            return float(upper)
    return float(LATENCY_BUCKETS_MS[-1])


def snapshot(day: str | None = None) -> dict:
    """当日指标快照（`/api/metrics` 的返回值）。"""
    counters, latency = store.metric_dump(day)
    lat_count = int(latency.get("count", 0))
    lat_sum = int(latency.get("sum", 0))

    tool_ok = _sum_where(counters, "tool", result="ok")
    tool_err = _sum_where(counters, "tool", result="err")
    req_ok = _sum_where(counters, "req", outcome="ok")
    req_err = _sum_where(counters, "req", outcome="error")
    req_blocked = _sum_where(counters, "req", outcome="blocked")
    req_need_login = _sum_where(counters, "req", outcome="need_login")
    req_total = sum(n for f, n in counters.items() if _parse_field(f)[0] == "req")
    ans_normal = _sum_where(counters, "answer", kind="normal")
    ans_refusal = _sum_where(counters, "answer", kind="refusal")
    order_preview = _sum_where(counters, "order", stage="preview")
    order_placed = _sum_where(counters, "order", stage="placed")

    return {
        "day": store.metric_day(day),
        "tokensToday": store.peek_tokens(),
        "latency": {
            "count": lat_count,
            "sumMs": lat_sum,
            "avgMs": round(lat_sum / lat_count, 1) if lat_count else 0.0,
            "p95Ms": percentile(latency, lat_count, 0.95),
            "buckets": {k: v for k, v in sorted(latency.items()) if k.startswith("le_")},
        },
        "counters": dict(sorted(counters.items())),
        "derived": {
            "requestsTotal": req_total,
            "toolSuccessRate": _ratio(tool_ok, tool_ok + tool_err),
            "refusalRate": _ratio(ans_refusal, ans_normal + ans_refusal),
            "errorRate": _ratio(req_err, req_total),
            "blockedRate": _ratio(req_blocked, req_total),
            "needLoginRate": _ratio(req_need_login, req_total),
            "orderConversion": _ratio(order_placed, order_preview),
            "reqByOutcome": {
                "ok": req_ok, "error": req_err, "blocked": req_blocked,
                "need_login": req_need_login,
            },
        },
    }


def status() -> dict:
    """诊断（验收脚本用）：配置与当日累计只读视图。"""
    return {"bucketsMs": list(LATENCY_BUCKETS_MS), "hints": len(REFUSAL_HINTS)}
