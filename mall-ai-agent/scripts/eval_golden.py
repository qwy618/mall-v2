"""M3.5 验收：金标集评估回归（检索层 + Agent 层 + 阈值复标）。

**和 smoke_m3_*.py 的分工**：
  smoke_* 回答「功能通不通」（24/24、36/36 这种布尔断言）；
  eval_golden 回答「质量涨没涨」——同一套固定题库每次改动都重跑，分数与
  eval/baseline.json 里的历史基线对比，分数下降就不该合并。

两层：
  A. retrieval 无 LLM：直连 retriever，测召回准确性 + **标定相似度阈值**
     （正样本最低分 vs 越界样本最高分，二者之间才是安全阈值区间）。
  B. agent 走真实 LLM：断言工具序列（价格类不得碰 search_knowledge）、
     拒答、回复金额必须来自工具返回值。慢且依赖模型，用 --layer 控制。

只读、可重复运行，失败即非零退出。

用法：
    ./.venv/Scripts/python.exe scripts/eval_golden.py                    # 检索层（默认）
    ./.venv/Scripts/python.exe scripts/eval_golden.py --layer agent      # Agent 层
    ./.venv/Scripts/python.exe scripts/eval_golden.py --layer all --update-baseline
    ./.venv/Scripts/python.exe scripts/eval_golden.py --case kb-review-01
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config                             # noqa: E402
from app.metrics import REFUSAL_HINTS as REFUSE_HINTS  # noqa: E402 —— 与生产指标同一份拒答词表
from app.rag import retriever, vector_store        # noqa: E402

GOLDEN = ROOT / "eval" / "golden_set.json"
BASELINE = ROOT / "eval" / "baseline.json"

# 金额表达式（与 app/rag/aggregate.py 出口清洗、smoke_m3_rag.py 同款）
AMOUNT_RE = re.compile(
    r"(?:¥|￥|\$)\s*\d+(?:\.\d{1,2})?"
    r"|\d+(?:\.\d{1,2})?\s*(?:元|块钱|块|人民币)"
)
NUM_RE = re.compile(r"\d+(?:\.\d{1,2})?")
# 工具返回里的价格字段（product_tools 把 lowestPrice 统一改名成 price，纯数字、无货币符号）
PRICE_FIELD_RE = re.compile(r'"price"\s*:\s*(\d+(?:\.\d+)?)')

# 拒答话术 vs 通用知识兜底话术（§9.3 第 3 条：拒答不得改用常识瞎编）
# ⚠️ REFUSE_HINTS 不在此定义：改为 import app.metrics.REFUSAL_HINTS，
# 让「金标集判定」与「生产拒答率指标」共用同一份词表，避免两套口径漂移。
FALLBACK_WORDS = [
    "一般来说", "一般来讲", "通常来说", "通常情况下", "市面上",
    "普遍认为", "据我所知", "一般市面上", "一般情况",
]

_ok = _fail = 0
_notes: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> bool:
    global _ok, _fail
    if cond:
        _ok += 1
        print(f"  [PASS] {label}" + (f"   {detail}" if detail else ""))
    else:
        _fail += 1
        print(f"  [FAIL] {label}" + (f"   {detail}" if detail else ""))
    return cond


def note(msg: str) -> None:
    _notes.append(msg)
    print(f"  [注意] {msg}")


def norm(s: str) -> str:
    """规范化：去空白 + 小写。用于商品名匹配（模型会写「小米 12 Pro」或「iPhone14」）。"""
    return re.sub(r"\s+", "", (s or "")).lower()


def amounts(s: str) -> set[float]:
    """抽出全部「金额」数字（只认带 ¥/元 的，避免把「6 条评价」「4.2 分」算进去）。"""
    out: set[float] = set()
    for m in AMOUNT_RE.findall(s or ""):
        for n in NUM_RE.findall(m):
            out.add(float(n))
    return out


def tool_prices(s: str) -> set[float]:
    """从工具返回里抽「价格集合」，作为「金额是不是编造的」的对照基准。

    工具返回是 JSON：product_tools 把价格统一改名成 `"price": 2999` —— 纯数字、
    **不带货币符号**。所以这里不能只靠 AMOUNT_RE，否则会把工具给出的真实价
    误判成编造（实测踩过：kb-price-01 的 2999 被判"编造"，其实工具返回里就有）。
    """
    out = {float(x) for x in PRICE_FIELD_RE.findall(s or "")}
    out |= amounts(s)          # 兜底：工具若直接把「¥2999」写进文本也能抓到
    return out


def load_cases(only: str | None = None) -> tuple[dict, list[dict]]:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    cases = data["cases"]
    if only:
        wanted = {x.strip() for x in only.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in wanted]
        missing = wanted - {c["id"] for c in cases}
        if missing:
            raise SystemExit(f"没有找到用例：{sorted(missing)}")
    return data, cases


# --------------------------------------------------------------------------
# A. 检索层
# --------------------------------------------------------------------------
def run_retrieval(cases: list[dict]) -> dict:
    print("\n=== A. 检索层（不依赖 LLM，用于阈值复标）===")
    print("  [主路径] 判定召回是否正确 + 提供标定分数；[open 裸查询] 鲁棒性诊断"
          "（LLM 若跳过 search_products 会漏多少）")
    rows: list[dict] = []
    for c in cases:
        if "retrieval" not in c["layers"]:
            continue
        exp = c["expect"]
        group = c["group"]
        mode = c.get("retrievalMode", "open")

        # 裸查询：任何模式都要跑。① 它是阈值标定的统一口径（全库 max，最能反映
        # L1 闸门真实面对的分数分布）② 它回答「LLM 若不先 search_products 就裸查，
        # 会漏掉多少」这个鲁棒性问题 —— 实测证明这个漏召回是真实存在的。
        op = retriever.search_knowledge_impl(c["query"])
        open_score = float(op.get("maxScore") or 0.0)
        open_ids = [int(it["productId"]) for it in (op.get("items") or [])]

        base = {
            "id": c["id"], "category": c["category"], "group": group, "mode": mode,
            "query": c["query"], "expectHit": bool(exp["hit"]),
            "openScore": round(open_score, 4), "openIds": open_ids[:5],
        }

        # 价格红线只观测、不判定：向量库里根本没有价格文档（库内无价格是设计如此），
        # 而「价格问题」与商品名高度相似 → L1 阈值**本就拦不住**这类查询。
        # 拦住它的责任在 LLM 路由（SYSTEM_PROMPT 规则 24），因此判定放在 agent 层
        # 的 forbidTools + amountFromTool，不在这里把观测值当失败。
        if group == "priceRedline":
            base.update({"maxScore": round(open_score, 4), "hit": bool(op.get("hit")),
                         "passed": True, "observe": True, "problems": []})
            rows.append(base)
            print(f"  [观测] {c['id']:<14} {open_score:.4f}   hit={str(bool(op.get('hit'))):<5} "
                  f"{c['category']}（不判定，见 agent 层）")
            continue

        # 指名商品的用例走两段式（与真实链路一致：先 search_products 拿 id，再限定检索）
        if mode == "filtered" and exp.get("productIds"):
            res = retriever.search_knowledge_impl(c["query"], product_ids=exp["productIds"])
        else:
            res = op
        hit = bool(res.get("hit"))
        score = float(res.get("maxScore") or 0.0)
        items = res.get("items") or []
        got_ids = [int(it["productId"]) for it in items]
        top = items[0]["name"] if items else ""

        problems: list[str] = []
        if hit != bool(exp["hit"]):
            problems.append(f"hit={hit} 期望 {exp['hit']}")
        if exp["hit"] and exp.get("productIds") and not (set(got_ids) & set(exp["productIds"])):
            problems.append(f"召回 {got_ids[:5]} 不含期望 {exp['productIds']}")
        if not exp["hit"] and hit:
            problems.append(f"不该命中却命中（{top[:18]}）")

        passed = not problems
        base.update({"maxScore": round(score, 4), "hit": hit,
                     "topProductId": got_ids[0] if got_ids else None, "topName": top,
                     "passed": passed, "problems": problems, "observe": False,
                     # 与阈值无关的问题（召回错误）—— 供阈值敏感度重算使用
                     "otherProblems": [p for p in problems if not p.startswith("hit=")]})

        # 鲁棒性诊断：主路径过了，但裸查询没召回期望商品 —— 说明该用例强依赖两段式
        if (passed and mode == "filtered" and exp.get("productIds")
                and not (set(open_ids) & set(exp["productIds"]))):
            base["openMiss"] = True

        rows.append(base)
        mark = "PASS" if passed else "FAIL"
        alt = "" if abs(score - open_score) < 1e-9 else f" / open {open_score:.4f}"
        tail = "  ← 裸查询漏召回，依赖两段式" if base.get("openMiss") else ""
        print(f"  [{mark}] {c['id']:<14} {score:.4f}{alt}  hit={str(hit):<5} "
              f"{c['category']}{tail}")
        if problems:
            print(f"         └─ {'; '.join(problems)}")

    judged = [r for r in rows if not r.get("observe")]
    return {
        "rows": rows,
        "pass": sum(r["passed"] for r in judged),
        "total": len(judged),
        "openMiss": [r["id"] for r in rows if r.get("openMiss")],
    }


def calibrate(rows: list[dict], open_miss: list[str] | None = None) -> dict:
    """阈值复标：正样本最低分 与 越界样本最高分 之间才是安全区间。

    口径 = **各用例在真实调用路径下的 maxScore**。这天然统一：
      · 越界问题：LLM 不会先搜商品 → 裸查全库，分数就是全库 max；
      · 指名商品的用例：LLM 会先 search_products 拿 id → 候选集内 max。
    两者都是 L1 闸门在实际链路上看到的那个数，可以直接比较。
    （不要统一改成裸查口径：kb-con-04 裸查拿到的 0.5709 来自 iPad 而非 OPPO，
      那是"命中但召回错商品"，不是它该有的分数。）
    """
    print("\n=== B. 阈值复标（RAG_SIM_THRESHOLD，口径：真实调用路径的 maxScore）===")
    pos = [r for r in rows if r["group"] == "positive"]
    neg = [r for r in rows if r["group"] == "offTopic"]
    red = [r for r in rows if r["group"] == "priceRedline"]

    if not pos or not neg:
        note("样本不足，跳过标定")
        return {}

    pos_min = min(r["maxScore"] for r in pos)
    pos_arg = min(pos, key=lambda r: r["maxScore"])
    neg_max = max(r["maxScore"] for r in neg)
    neg_arg = max(neg, key=lambda r: r["maxScore"])
    cur = config.RAG_SIM_THRESHOLD

    print(f"  正样本 {len(pos)} 条：最低 {pos_min:.4f}（{pos_arg['id']}）"
          f"  平均 {sum(r['maxScore'] for r in pos) / len(pos):.4f}")
    print(f"  越界样本 {len(neg)} 条：最高 {neg_max:.4f}（{neg_arg['id']}）"
          f"  平均 {sum(r['maxScore'] for r in neg) / len(neg):.4f}")
    if red:
        red_max = max(r["maxScore"] for r in red)
        red_arg = max(red, key=lambda r: r["maxScore"])
        print(f"  价格红线 {len(red)} 条：最高 {red_max:.4f}（{red_arg['id']}）"
              f" —— 必然 > 阈值，由提示词规则 24 兜底，不参与标定")

    out: dict = {
        "positiveMin": round(pos_min, 4), "positiveMinCase": pos_arg["id"],
        "offTopicMax": round(neg_max, 4), "offTopicMaxCase": neg_arg["id"],
        "priceRedlineMax": round(max((r["maxScore"] for r in red), default=0.0), 4),
        "current": cur, "sample": len(pos) + len(neg),
    }

    if neg_max < pos_min:
        lo, hi = neg_max, pos_min
        # 目标不是"偏严"，而是**最大化两侧的最小余量**：阈值离两个边界都尽量远，
        # 分数抖动才不会翻转判定。一味偏严会把边缘正样本推下悬崖 ——
        # 实测 0.52 就误杀 kb-con-04（0.5022），而 0.48 能同时保住 19/19 与 0/6。
        rec = round((lo + hi) / 2, 2)
        out.update({"separable": True, "safeLo": round(lo, 4), "safeHi": round(hi, 4),
                    "recommend": rec, "marginLo": round(rec - lo, 4),
                    "marginHi": round(hi - rec, 4)})
        print(f"  安全区间：({lo:.4f}, {hi:.4f}]   推荐 {rec:.2f}"
              f"（两侧最小余量最大化：下 {rec - lo:.4f} / 上 {hi - rec:.4f}）")
        if lo < cur <= hi:
            print(f"  当前阈值 {cur} 在区间内 ✓（距下界 {cur - lo:.4f}，距上界 {hi - cur:.4f}）")
            if cur - lo < 0.02:
                note(f"当前阈值 {cur} 距最危险的越界样本仅 {cur - lo:.4f}，余量过薄"
                     f"（一次 embedding 抖动就会漏放）→ 建议改为 {rec}")
        else:
            print(f"  ⚠️ 当前阈值 {cur} **不在**安全区间内 → 应改为 {rec}")
            note(f"阈值越界：当前 {cur}，建议 {rec}（安全区间 ({lo:.4f}, {hi:.4f}]）")
    else:
        worst = [r for r in neg if r["maxScore"] >= pos_min]
        out.update({"separable": False, "overlap": True,
                    "offenders": [r["id"] for r in worst],
                    "recommend": round(pos_min, 2)})
        print(f"  ⚠️ 存在重叠：有 {len(worst)} 条越界样本分数 ≥ 正样本最低分")
        for r in worst:
            print(f"     · {r['id']} {r['maxScore']:.4f}（{r['query'][:20]}）")
        note("阈值区间重叠：小数据量下的已知局限，靠提示词层（L2）兜底")

    if open_miss:
        note(f"裸查询漏召回 {len(open_miss)} 条：{open_miss} —— "
             f"这些用例强依赖「先 search_products 再限定检索」的两段式，"
             f"LLM 若不走两段式会漏（与阈值无关，是 embedding 对型号词表征弱）")

    return out


def threshold_sweep(rows: list[dict],
                    cands: tuple[float, ...] = (0.44, 0.46, 0.48, 0.50, 0.52, 0.54)) -> dict:
    """阈值敏感度：把阈值当自变量，看「该答的漏答」与「该拒的漏放」各错几条。

    这是选阈值的**代价表** —— 结论不是"某值最好"，而是"每往上抬一格，
    拿多少拒答率换多少幻觉风险"。决策原则固定：幻觉代价 > 拒答代价。
    """
    print("\n=== C. 阈值敏感度（拿拒答率换幻觉风险，看这笔交易划不划算）===")
    judged = [r for r in rows if not r.get("observe")]
    pos = [r for r in judged if r["group"] == "positive"]
    neg = [r for r in judged if r["group"] == "offTopic"]

    print(f"  {'阈值':<6}{'正样本命中':<12}{'越界放行':<12}{'用例通过':<10}判定")
    table: dict[str, dict] = {}
    for t in cands:
        p_hit = sum(1 for r in pos if r["maxScore"] >= t)
        n_bad = sum(1 for r in neg if r["maxScore"] >= t)
        passed = sum(1 for r in judged
                     if (r["maxScore"] >= t) == r["expectHit"] and not r["otherProblems"])
        total = len(judged)
        flag = ""
        if n_bad:
            flag = f"← 放行 {n_bad} 条越界（幻觉风险）"
        elif p_hit < len(pos):
            flag = f"← 漏答 {len(pos) - p_hit} 条正样本（体验损失）"
        else:
            flag = "← 两侧都不错"
        print(f"  {t:<6.2f}{f'{p_hit}/{len(pos)}':<12}{f'{n_bad}/{len(neg)}':<12}"
              f"{f'{passed}/{total}':<10}{flag}")
        table[f"{t:.2f}"] = {"posHit": p_hit, "posTotal": len(pos),
                             "negLeak": n_bad, "negTotal": len(neg),
                             "passed": passed, "total": total}
    return table


def scan_redlines() -> bool:
    """§9.3 第 1 条：向量库 payload 不得含价格/库存。CI 级红线。"""
    print("\n=== D. 红线扫描（向量库不得含价格/库存）===")
    allp = vector_store.scroll_all()
    bad_fields, bad_amounts = [], []
    for p in allp:
        pl = p["payload"]
        for k in ("price", "lowestPrice", "stock", "lockStock", "productSn"):
            if k in pl:
                bad_fields.append((pl.get("productId"), k))
        for m in AMOUNT_RE.findall(json.dumps(pl, ensure_ascii=False)):
            bad_amounts.append((pl.get("productId"), m))
    check("payload 无价格/库存字段", not bad_fields, str(bad_fields[:3]))
    check("payload 无金额表达式", not bad_amounts, str(bad_amounts[:5]))
    return not bad_fields and not bad_amounts


# --------------------------------------------------------------------------
# D. Agent 层（真实 LLM）
# --------------------------------------------------------------------------
def _tool_names(msgs) -> list[str]:
    out = []
    for m in msgs:
        for tc in (getattr(m, "tool_calls", None) or []):
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if name:
                out.append(str(name))
    return out


def _tool_text(msgs) -> str:
    return "\n".join(str(getattr(m, "content", "")) for m in msgs
                     if getattr(m, "type", "") == "tool")


def judge_agent(exp: dict, names: list[str], answer: str, tool_text: str,
                query: str = "") -> list[str]:
    problems: list[str] = []

    for t in exp.get("forbidTools") or []:
        if t in names:
            problems.append(f"禁止调用 {t} 却调用了")

    order = exp.get("toolOrder") or []
    if order:
        idx, cursor = [], 0
        for t in names:                        # 按首次出现位置判定相对顺序
            if t in order and t not in idx:
                idx.append(t)
        if [t for t in order if t in names] != order:
            problems.append(f"缺少必需工具（期望 {order}，实际 {idx}）")
        else:
            pos = [names.index(t) for t in order]
            if pos != sorted(pos):
                problems.append(f"工具顺序不对（期望 {order}，实际 {names}）")

    must_any = exp.get("mustCallAny") or []
    if must_any and not (set(must_any) & set(names)):
        problems.append(f"未调用必需的实时工具（{must_any}）")

    mention = exp.get("mentionAny") or []
    if mention and not any(norm(m) in norm(answer) for m in mention):
        problems.append(f"回复未提及期望商品名（{mention[:2]}）")

    if exp.get("refuse"):
        hit_refuse = any(h in answer for h in REFUSE_HINTS)
        fallback = [w for w in FALLBACK_WORDS if w in answer]
        if not hit_refuse:
            problems.append("未给出明确的拒答话术")
        if fallback:
            problems.append(f"拒答时使用了通用知识兜底（{fallback[:2]}）")
    elif not exp.get("refuse"):
        bad = [w for w in FALLBACK_WORDS if w in answer]
        if bad:
            problems.append(f"回答使用了未经验证的兜底话术（{bad[:2]}）")

    if exp.get("amountFromTool"):
        # 合法来源 = 工具返回值 ∪ 用户 query 里的数字。
        # 后者必须有：模型复述用户给的约束（「2000 元以内」）不是编造价格，
        # 漏掉这一项会把正常回答误判成幻觉（实测踩过：kb-mix-01）。
        allowed = tool_prices(tool_text) | {float(x) for x in NUM_RE.findall(query or "")}
        invented = sorted(a for a in amounts(answer) if a not in allowed)
        if invented:
            problems.append(f"金额非来自工具返回值（编造 {invented}）")

    return problems


def run_agent(cases: list[dict]) -> dict:
    from langchain_core.messages import HumanMessage
    from app.agent import build_agent

    print("\n=== E. Agent 层（真实 LLM，逐条独立会话、无记忆污染）===")
    agent = build_agent()
    rows: list[dict] = []
    for c in cases:
        if "agent" not in c["layers"]:
            continue
        exp = c["expect"]
        print(f"\n  ── {c['id']}（{c['category']}）：{c['query']}")
        try:
            res = agent.invoke({"messages": [HumanMessage(content=c["query"])]})
            msgs = res["messages"]
            names = _tool_names(msgs)
            answer = str(getattr(msgs[-1], "content", "") or "")
        except Exception as e:                     # noqa: BLE001
            print(f"  [FAIL] 调用异常：{e}")
            _fail += 1
            rows.append({"id": c["id"], "passed": False, "problems": [f"异常 {e}"]})
            continue

        print(f"     工具序列：{names or '（无）'}")
        print(f"     回复：{answer[:120].replace(chr(10), ' ')}")

        problems = judge_agent(exp, names, answer, _tool_text(msgs), c["query"])
        passed = check(f"{c['id']} {c['category']}",
                       not problems, "; ".join(problems))
        rows.append({"id": c["id"], "passed": passed, "tools": names,
                     "answer": answer[:400], "problems": problems})
    return {"rows": rows, "pass": sum(r["passed"] for r in rows), "total": len(rows)}


# --------------------------------------------------------------------------
# 留档
# --------------------------------------------------------------------------
def save_baseline(ret: dict | None, agt: dict | None, calib: dict | None,
                  sweep: dict | None = None) -> None:
    old: dict = {}
    if BASELINE.exists():
        try:
            old = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:                          # noqa: BLE001
            old = {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    def block(cur: dict, prev: dict) -> dict:
        out = {"pass": cur["pass"], "total": cur["total"],
               "rate": round(cur["pass"] / max(cur["total"], 1), 4),
               "updatedAt": now}
        if prev:
            out["prevRate"] = prev.get("rate")
            out["delta"] = round(out["rate"] - float(prev.get("rate") or 0), 4)
        return out

    data = dict(old)
    data["collection"] = config.RAG_COLLECTION
    data["embedModel"] = config.EMBED_MODEL
    if ret:
        data["retrieval"] = block(ret, old.get("retrieval", {}))
        judged = [r for r in ret["rows"] if not r.get("observe")]
        data["retrieval"]["byCategory"] = {
            cat: {
                "pass": sum(r["passed"] for r in judged if r["category"] == cat),
                "total": sum(1 for r in judged if r["category"] == cat),
            }
            for cat in dict.fromkeys(r["category"] for r in judged)
        }
        # 留档用 openScore（全库裸查询），与阈值标定同口径
        data["retrieval"]["scores"] = {r["id"]: r["openScore"] for r in ret["rows"]}
        data["retrieval"]["openMiss"] = ret.get("openMiss") or []
    if agt:
        data["agent"] = block(agt, old.get("agent", {}))
    if calib:
        data["threshold"] = dict(calib)
        if sweep:
            data["threshold"]["sweep"] = sweep
    BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\n基线已写入 {BASELINE.relative_to(ROOT)}")


def diff_prev(block_name: str, ret_or_agt: dict) -> None:
    """和上次基线对比：分数下降要显式喊出来。"""
    if not BASELINE.exists():
        print(f"\n（无历史基线，本次为首次留档）")
        return
    try:
        old = json.loads(BASELINE.read_text(encoding="utf-8")).get(block_name, {})
    except Exception:                              # noqa: BLE001
        return
    if not old:
        return
    cur = ret_or_agt["pass"] / max(ret_or_agt["total"], 1)
    prev = float(old.get("rate") or 0)
    delta = cur - prev
    tag = "↑" if delta > 0 else ("↓ 回归！" if delta < 0 else "→ 持平")
    print(f"\n与基线对比（{block_name}）：本次 {cur:.1%} vs 上次 {prev:.1%}  {tag}")


def main() -> int:
    ap = argparse.ArgumentParser(description="M3.5 金标集评估回归")
    ap.add_argument("--layer", default="retrieval",
                    choices=["retrieval", "agent", "all"])
    ap.add_argument("--case", default=None, help="只跑指定用例，逗号分隔（调试用）")
    ap.add_argument("--update-baseline", action="store_true",
                    help="把本次结果写入 eval/baseline.json")
    args = ap.parse_args()

    data, cases = load_cases(args.case)
    print(f"题库 {GOLDEN.relative_to(ROOT)}  v{data['version']}（{data['updatedAt']}）"
          f"  本次 {len(cases)} 条 / 共 {len(data['cases'])} 条")
    print(f"collection={config.RAG_COLLECTION}  dims={config.EMBED_DIM}  "
          f"threshold={config.RAG_SIM_THRESHOLD}  topK={config.RAG_TOP_K}")

    ret = agt = calib = sweep = None
    redline_ok = True

    if args.layer in ("retrieval", "all"):
        ret = run_retrieval(cases)
        calib = calibrate(ret["rows"], ret.get("openMiss"))
        sweep = threshold_sweep(ret["rows"])
        redline_ok = scan_redlines()

    if args.layer in ("agent", "all"):
        agt = run_agent(cases)

    if ret:
        diff_prev("retrieval", ret)
    if agt:
        diff_prev("agent", agt)

    if args.update_baseline:
        save_baseline(ret, agt, calib, sweep)

    # ---------------- 汇总 ----------------
    print(f"\n{'=' * 56}")
    if ret:
        print(f"检索层：{ret['pass']}/{ret['total']} 通过"
              f"（{ret['pass'] / max(ret['total'], 1):.1%}）")
        if ret.get("openMiss"):
            print(f"  裸查询漏召回 {len(ret['openMiss'])} 条：{', '.join(ret['openMiss'])}")
            print(f"  （这些用例走两段式才稳 —— LLM 若跳过 search_products 会漏）")
    if agt:
        print(f"Agent 层：{agt['pass']}/{agt['total']} 通过"
              f"（{agt['pass'] / max(agt['total'], 1):.1%}）")
    print(f"红线扫描：{'通过' if redline_ok else '❌ 违规'}")
    if _notes:
        print("注意事项：")
        for n in _notes:
            print(f"  · {n}")
    print(f"断言合计：{_ok} 通过 / {_fail} 失败")
    print("=" * 56)
    print("提示：加 --update-baseline 把本次分数留档为下次的对比基线。")

    return 0 if (_fail == 0 and redline_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
