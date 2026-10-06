"""M3.5 + M4.4 验收：金标集评估回归（检索层 + Agent 层 + 业务类 + 阈值复标）。

**和 smoke_*.py 的分工**：
  smoke_* 回答「功能通不通」（24/24、36/36 这种布尔断言）；
  eval_golden 回答「质量涨没涨」——同一套固定题库每次改动都重跑，分数与
  eval/baseline.json 里的历史基线对比，分数下降就不该合并。

三层：
  A. retrieval 无 LLM：直连 retriever，测召回准确性 + **标定相似度阈值**
     （正样本最低分 vs 越界样本最高分，二者之间才是安全阈值区间）。
  B. agent 走真实 LLM（知识类）：断言工具序列（价格类不得碰 search_knowledge）、
     拒答、回复金额必须来自工具返回值。慢且依赖模型，用 --layer 控制。
  C. agent 走真实 LLM（业务类，M4.4）：找商品 / 条件筛选 / 详情 / 加购 / 下单，
     **多轮**（turns，同一会话累积上下文），断言业务硬约束：
       · priceMax     —— 展示的每款商品价格都 ≤ 上限（按工具返回的真实 price 核）
       · args         —— 工具**入参**断言（如 add_to_cart 的 quantity 必须等于用户说的数）
       · requireConfirmOnce —— 全程必须出确认单、且绝不允许 place_order
       · noShowOnEmpty / answerHasNumber / answerAny / needLogin
     加购/下单需要登录态：提供 token 才跑，否则标 SKIP（不算失败）。

只读（加购/下单会动测试会员的购物车）、可重复运行，失败即非零退出。

用法：
    ./.venv/Scripts/python.exe scripts/eval_golden.py                    # 检索层（默认）
    ./.venv/Scripts/python.exe scripts/eval_golden.py --layer agent      # Agent 层（知识类）
    ./.venv/Scripts/python.exe scripts/eval_golden.py --layer agent --group business
    ./.venv/Scripts/python.exe scripts/eval_golden.py --layer all --update-baseline
    ./.venv/Scripts/python.exe scripts/eval_golden.py --case kb-review-01

登录态（业务类用例）三种给法，优先级从高到低：
    --token <JWT>                    直接给已登录 token
    EVAL_MEMBER_TOKEN=<JWT>          同上，环境变量
    EVAL_MEMBER_PHONE/EVAL_MEMBER_PASSWORD   脚本自动登录换取 token（推荐，免手工过期）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config                             # noqa: E402
from app.metrics import REFUSAL_HINTS as REFUSE_HINTS  # noqa: E402 —— 与生产指标同一份拒答词表
from app.rag import retriever, vector_store        # noqa: E402
from app.tools import mall_client                  # noqa: E402 —— 自动登录换取会员 token 用

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
def _tool_calls(msgs) -> list[dict]:
    """抽出本轮全部工具调用（名字 + 入参）。

    入参是 M4.4 业务类断言的关键：只看「回复里写了 2 件」很容易被模型的
    漂亮措辞骗过，而 `add_to_cart(quantity=2)` 是硬事实。
    LangChain 的 tool_calls 在不同版本里可能是 dict 也可能是带属性的对象，故双通路取。
    """
    out: list[dict] = []
    for m in msgs:
        for tc in (getattr(m, "tool_calls", None) or []):
            if isinstance(tc, dict):
                name, args = tc.get("name"), tc.get("args")
            else:
                name, args = getattr(tc, "name", None), getattr(tc, "args", None)
            if name:
                out.append({"name": str(name), "args": args if isinstance(args, dict) else {}})
    return out


def _tool_names(msgs) -> list[str]:
    return [c["name"] for c in _tool_calls(msgs)]


def _tool_text(msgs) -> str:
    return "\n".join(str(getattr(m, "content", "")) for m in msgs
                     if getattr(m, "type", "") == "tool")


def _msg_text_by_name(msgs, name: str) -> str:
    """取某个工具**最后一条**返回内容。

    LangChain 的工具消息本身不带工具名，但 AIMessage.tool_calls 里有
    `id`，ToolMessage 有 `tool_call_id` —— 用 id 反查，比正则猜名字可靠。
    """
    ids: list[str] = []
    for m in msgs:
        for tc in (getattr(m, "tool_calls", None) or []):
            n = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if n == name:
                i = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                if i:
                    ids.append(str(i))
    if not ids:
        return ""
    want = ids[-1]
    for m in msgs:
        if (getattr(m, "tool_call_id", None) or "") == want:
            return str(getattr(m, "content", "") or "")
    return ""


def _price_map(msgs) -> dict[int, float]:
    """从 search_products 的返回里建 {商品id: 价格}，作为「展示价是否超上限」的对照基准。

    取全部历史里的搜索结果（多轮时第一轮搜出的商品在第二轮依然有效），
    后出现的同 id 覆盖先出现的（价格以最新一次为准）。
    """
    out: dict[int, float] = {}
    for m in msgs:
        if getattr(m, "type", "") != "tool":
            continue
        txt = str(getattr(m, "content", "") or "")
        if '"price"' not in txt or '"name"' not in txt:
            continue
        try:
            items = json.loads(txt)
        except ValueError:
            continue
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            pid, price = it.get("id"), it.get("price")
            if pid is not None and isinstance(price, (int, float)):
                out[int(pid)] = float(price)
    return out


def _shown_ids(msgs) -> list[int]:
    """show_products 实际展示出去的商品 id（取最后一次调用的入参）。"""
    for c in reversed(_tool_calls(msgs)):
        if c["name"] != "show_products":
            continue
        raw = c["args"].get("product_ids")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                raw = re.findall(r"\d+", raw)
        if isinstance(raw, list):
            return [int(x) for x in raw if str(x).strip().lstrip("-").isdigit()]
        return []
    return []


def _loose_eq(a, b) -> bool:
    """参数比较：容忍 "2" vs 2（LLM 常把数字写成字符串）。"""
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def _search_items(msgs) -> list[dict]:
    """最后一次 search_products 的返回（商品列表）。"""
    txt = _msg_text_by_name(msgs, "search_products").strip()
    if not txt:
        return []
    try:
        items = json.loads(txt)
    except ValueError:
        return []
    return [it for it in items if isinstance(it, dict)] if isinstance(items, list) else []


# 金标用例里「参与判定」的字段。空断言集必须报错，否则用例会静默通过 ——
# 实测踩过：biz-guard-01 只写了 needLogin，在有 token 的场景下一路走到判定，
# 因为没有任何断言而被判 PASS，这是最危险的一种假绿。
_ASSERT_KEYS = {"forbidTools", "toolOrder", "mustCallAny", "args", "mentionAny",
                "refuse", "amountFromTool", "priceMax", "noShowOnEmpty",
                "requireConfirmOnce", "answerHasNumber", "answerAny"}


def judge_agent(exp: dict, msgs, answer: str, tool_text: str,
                query: str = "", all_msgs=None) -> list[str]:
    """判定一轮对话。msgs=本轮消息切片，all_msgs=整段会话（用于跨轮断言）。

    注意签名从「names 列表」改成「msgs 切片」：M4.4 要断言工具**入参**，
    只传名字不够用了。
    """
    problems: list[str] = []
    names = _tool_names(msgs)

    if not (_ASSERT_KEYS & set(exp)):
        return [f"用例未声明任何判定条件（{sorted(exp)}）—— 空断言会假绿，先补 expect"]

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

    # ---- M4.4：工具入参断言 ----
    for tool_name, kv in (exp.get("args") or {}).items():
        calls = [c for c in _tool_calls(msgs) if c["name"] == tool_name]
        if not calls:
            problems.append(f"{tool_name} 未调用，无法校验参数 {kv}")
            continue
        if not any(all(_loose_eq(c["args"].get(k), v) for k, v in kv.items())
                   for c in calls):
            actual = [c["args"] for c in calls][:2]
            problems.append(f"{tool_name} 入参不符（期望 {kv}，实际 {actual}）")

    mandate = exp.get("mentionAny") or []
    if mandate and not any(norm(m) in norm(answer) for m in mandate):
        problems.append(f"回复未提及期望商品名（{mandate[:2]}）")

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

    # ---- M4.4：业务硬约束 ----
    if exp.get("priceMax") is not None:
        lim = float(exp["priceMax"])
        pmap = _price_map(all_msgs if all_msgs is not None else msgs)
        shown = _shown_ids(all_msgs if all_msgs is not None else msgs)
        over = [(i, pmap[i]) for i in shown if i in pmap and pmap[i] > lim]
        unknown = [i for i in shown if i not in pmap]
        if over:
            problems.append(f"展示商品价格超出 {lim:g}：{over[:3]}")
        if unknown:
            problems.append(f"展示的商品 {unknown[:3]} 在搜索结果里查不到价格（疑似编造 id）")

    if exp.get("noShowOnEmpty"):
        # 规则 6 的两种触发场景都覆盖：
        #   ① 搜索压根没结果；② 有结果但**没有一款满足用户的硬条件**（如预算）。
        # 只看①会漏掉最常见的一种幻觉：预算 50 元、搜出一堆 649 元的还照样展示。
        scope = all_msgs if all_msgs is not None else msgs
        items = _search_items(scope)
        lim = exp.get("priceMax")
        if lim is None:
            eligible = items
        else:
            eligible = [it for it in items
                        if isinstance(it.get("price"), (int, float))
                        and float(it["price"]) <= float(lim)]
        if not eligible and "show_products" in _tool_names(scope):
            why = "搜索无结果" if not items else f"没有一款商品满足 ≤{float(lim):g} 元"
            problems.append(f"{why}，却仍调用 show_products 展示（硬凑）")

    if exp.get("requireConfirmOnce"):
        names_all = _tool_names(all_msgs if all_msgs is not None else msgs)
        if "place_order" in names_all:
            problems.append("未经用户点击确认就调用了 place_order")
        if "preview_order" not in names_all:
            problems.append("未生成订单确认单（preview_order 从未调用）")

    if exp.get("answerHasNumber") and not re.search(r"\d", answer or ""):
        problems.append("回复未给出任何数字（缺数量时必须先报库存数再问几件）")

    for w in exp.get("answerAny") or []:
        if w in (answer or ""):
            break
    else:
        if exp.get("answerAny"):
            problems.append(f"回复未包含任一预期措辞（{exp['answerAny']}）")

    return problems


def resolve_member_token(token_arg: str | None) -> str | None:
    """拿一个可用会员 token（业务类用例需要）：显式 token > 环境变量 > 自动登录。

    都取不到返回 None —— 调用方把 requiresLogin 的用例标 SKIP，**不算失败**：
    评测套件不该因为「没配测试账号」整体变红，那样会把真实的模型回归淹掉。
    """
    tok = (token_arg or os.getenv("EVAL_MEMBER_TOKEN") or "").strip()
    if tok:
        print("  登录态：使用显式 token（--token / EVAL_MEMBER_TOKEN）")
        return tok
    phone = (os.getenv("EVAL_MEMBER_PHONE") or "").strip()
    pwd = os.getenv("EVAL_MEMBER_PASSWORD") or ""
    if not (phone and pwd):
        return None
    try:
        data = mall_client.api_post(config.PORTAL_BASE_URL, "/member/login",
                                    params={"phone": phone, "password": pwd})
    except Exception as e:                             # noqa: BLE001
        print(f"  登录态：自动登录失败（{e}）")
        return None
    res = data.get("data") or {}
    body_token, head = res.get("token") or "", res.get("tokenHead") or ""
    if not body_token:
        print("  登录态：自动登录响应里没有 token")
        return None
    print(f"  登录态：已用 {phone[:3]}****{phone[-4:]} 自动登录换取 token")
    return f"{head}{body_token}".strip()


def _clear_cart(token: str) -> int:
    """清空测试会员的购物车，保证用例之间互不污染。

    🔴 为什么必须清：`/cart/add` 对**同一个 SKU 是累加数量**的。不清的话
    biz-cart-01 加 2 件、biz-order-01 再加 1 件 → 确认卡上是 3 件、4 件、5 件，
    用例之间互相改变对方的输入，断言就不可重复了（实测就是这么飘的）。
    portal 没有 /cart/clear，只能按 cartItemId 逐条删。
    只动测试会员的购物车（可逆、不产生订单）。
    """
    try:
        items = mall_client.api_get(config.PORTAL_BASE_URL, "/cart/list",
                                    token=token).get("data") or []
    except Exception as e:                             # noqa: BLE001
        print(f"     [warn] 读取购物车失败，跳过清理：{e}")
        return 0
    n = 0
    for it in items:
        cid = it.get("cartItemId")
        if cid is None:
            continue
        try:
            mall_client.api_delete(config.PORTAL_BASE_URL, "/cart/delete",
                                   params={"cartItemId": cid}, token=token)
            n += 1
        except Exception as e:                         # noqa: BLE001
            print(f"     [warn] 删除购物车条目 {cid} 失败：{e}")
    return n


def run_agent(cases: list[dict], token: str | None = None,
              reset_cart: bool = True) -> dict:
    from langchain_core.messages import HumanMessage
    from app.agent import build_agent
    from app.tools.mall_client import NeedLoginError, resolve_member_id
    from app.tools.order_tools import current_member, current_session, current_token

    print("\n=== E. Agent 层（真实 LLM）===")
    print("  单轮用例 → 独立会话（无记忆污染）；多轮用例（turns）→ 同一会话累积上下文，"
          "断言默认只对**最后一轮**生效，中间轮用 expect.perTurn 显式声明")
    agent = build_agent()
    member_id = resolve_member_id(token) if token else None
    if token:
        print(f"  登录会员：memberId={member_id}")

    rows: list[dict] = []
    for c in cases:
        if "agent" not in c["layers"]:
            continue
        exp = c["expect"]

        if c.get("requiresLogin") and not token:
            print(f"\n  ── {c['id']}（{c['category']}）：需要登录态 —— SKIP")
            note(f"{c['id']} 已跳过（缺会员 token，见文件头「登录态」三种给法）")
            rows.append({"id": c["id"], "category": c["category"],
                         "skipped": True, "problems": []})
            continue

        # needLogin 用例的语义就是「**未登录时**必须走登录引导」——
        # 有 token 时必须强行摘掉，否则它会一路成功，而空断言集又会假绿。
        use_token = None if exp.get("needLogin") else token
        if use_token and c.get("requiresLogin") and reset_cart:
            n = _clear_cart(use_token)
            print(f"     [前置] 已清空购物车 {n} 条（保证用例间不互相污染）")

        turns = c.get("turns") or [c["query"]]
        multi = f" {len(turns)} 轮" if len(turns) > 1 else ""
        print(f"\n  ── {c['id']}（{c['category']}）{multi}：{' | '.join(turns)}")

        # 上下文与 main.py 完全一致：token/session/member 经 ContextVar 透传给工具
        sess = f"eval-{c['id']}"
        t_ctx = current_token.set(use_token)
        s_ctx = current_session.set(sess)
        m_ctx = current_member.set(member_id if use_token else None)
        history: list = []
        records: list[dict] = []
        try:
            for qi, q in enumerate(turns):
                history.append(HumanMessage(content=q))
                res = agent.invoke({"messages": list(history)})
                full = list(res["messages"])
                delta = full[len(history):]          # 本轮新增的 AI/Tool 消息
                history = full
                ans = str(getattr(full[-1], "content", "") or "")
                records.append({"turn": qi + 1, "query": q, "delta": delta,
                                "names": _tool_names(delta), "answer": ans})
                print(f"     T{qi + 1} 工具：{records[-1]['names'] or '（无）'}")
                print(f"          回复：{ans[:110].replace(chr(10), ' ')}")
        except NeedLoginError:
            ok = bool(exp.get("needLogin"))
            check(f"{c['id']} {c['category']}", ok,
                  "未登录 → 正确抛出 NeedLoginError（前端据此走登录引导）" if ok
                  else "未登录状态下不该需要登录")
            rows.append({"id": c["id"], "category": c["category"], "passed": ok,
                         "needLogin": True,
                         "tools": [n for r in records for n in r["names"]],
                         "problems": [] if ok else ["意外 NeedLoginError"]})
            continue
        except Exception as e:                       # noqa: BLE001
            print(f"  [FAIL] 调用异常：{e}")
            _fail += 1
            rows.append({"id": c["id"], "category": c["category"], "passed": False,
                         "problems": [f"异常 {e}"]})
            continue
        finally:
            current_token.reset(t_ctx)
            current_session.reset(s_ctx)
            current_member.reset(m_ctx)

        per_turn = {pt["turn"]: pt for pt in (exp.get("perTurn") or [])}
        problems: list[str] = []
        for i, r in enumerate(records):
            if i == len(records) - 1:
                exp_r = {k: v for k, v in exp.items() if k != "perTurn"}
            elif r["turn"] in per_turn:
                exp_r = {}                               # 中间轮：只跑显式声明的检查
            else:
                continue
            exp_r.update({k: v for k, v in per_turn.get(r["turn"], {}).items() if k != "turn"})
            got = judge_agent(exp_r, r["delta"], r["answer"],
                              _tool_text(r["delta"]), r["query"], all_msgs=history)
            problems += [f"T{r['turn']} {x}" for x in got]

        passed = check(f"{c['id']} {c['category']}", not problems, "; ".join(problems))
        rows.append({
            "id": c["id"], "category": c["category"], "passed": passed,
            "tools": [n for r in records for n in r["names"]],
            "turns": [{"turn": r["turn"], "query": r["query"], "tools": r["names"],
                       "answer": r["answer"][:300]} for r in records],
            "problems": problems,
        })

    judged = [r for r in rows if not r.get("skipped")]
    return {"rows": rows, "pass": sum(r["passed"] for r in judged),
            "total": len(judged),
            "skipped": [r["id"] for r in rows if r.get("skipped")]}


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
        # M4.4：业务类单独留档 —— 它们依赖登录态/真实购物车，波动原因和知识类不同，
        # 混在一个数字里看不出是哪边退化了
        biz = [r for r in agt["rows"]
               if str(r.get("id", "")).startswith("biz-") and not r.get("skipped")]
        data["agent"]["business"] = {
            "pass": sum(1 for r in biz if r["passed"]), "total": len(biz),
            "skipped": agt.get("skipped") or [],
        }
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
    ap = argparse.ArgumentParser(description="M3.5+M4.4 金标集评估回归")
    ap.add_argument("--layer", default="retrieval",
                    choices=["retrieval", "agent", "all"])
    ap.add_argument("--case", default=None, help="只跑指定用例，逗号分隔（调试用）")
    ap.add_argument("--group", default=None,
                    help="只跑指定 group（positive / offTopic / priceRedline / business）")
    ap.add_argument("--token", default=None,
                    help="会员 JWT（业务类加购/下单用；亦可用 EVAL_MEMBER_TOKEN 或自动登录）")
    ap.add_argument("--no-cart-reset", action="store_true",
                    help="登录类用例前不清空购物车（默认会清，见 _clear_cart 的说明）")
    ap.add_argument("--update-baseline", action="store_true",
                    help="把本次结果写入 eval/baseline.json")
    args = ap.parse_args()

    data, cases = load_cases(args.case)
    if args.group:
        wanted = {g.strip() for g in args.group.split(",") if g.strip()}
        cases = [c for c in cases if c["group"] in wanted]
        if not cases:
            raise SystemExit(f"group={args.group} 没有用例")
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
        token = resolve_member_token(args.token)
        if token and not args.no_cart_reset:
            print("  ⚠️ 加购类用例前会清空该测试会员的购物车（--no-cart-reset 可关闭）")
        agt = run_agent(cases, token=token, reset_cart=not args.no_cart_reset)

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
        biz = [r for r in agt["rows"] if r.get("category") and _is_biz(r)]
        if biz:
            bp = sum(r.get("passed") for r in biz if not r.get("skipped"))
            bt = sum(1 for r in biz if not r.get("skipped"))
            print(f"  其中业务类：{bp}/{bt} 通过")
        if agt.get("skipped"):
            print(f"  ⏭ 跳过 {len(agt['skipped'])} 条（需登录态）：{', '.join(agt['skipped'])}")
            print(f"     → 给上 token 即可纳入：--token <JWT> 或 EVAL_MEMBER_PHONE/PASSWORD")
    print(f"红线扫描：{'通过' if redline_ok else '❌ 违规'}")
    if _notes:
        print("注意事项：")
        for n in _notes:
            print(f"  · {n}")
    print(f"断言合计：{_ok} 通过 / {_fail} 失败")
    print("=" * 56)
    print("提示：加 --update-baseline 把本次分数留档为下次的对比基线。")

    return 0 if (_fail == 0 and redline_ok) else 1


def _is_biz(row: dict) -> bool:
    """业务类行判定：靠 category 无法回查 group，用 id 前缀（biz-）最省事且稳定。"""
    return str(row.get("id", "")).startswith("biz-")


if __name__ == "__main__":
    raise SystemExit(main())
