"""评价聚合：把某商品的全部**公开**评价压成一份"口碑文档"（review_summary）。

这是「评价数据 → 语义道」的**唯一入口**，因此也是防幻觉的第一道闸门：
  · 输入只有评价原文 + 商品名（不含任何外部知识）；
  · 输出被强制成固定 JSON schema（pros / cons / quotes / text）；
  · 出口再做一次金额清洗（纵深防御，prompt 已禁止，但模型不保证听话）。

聚合而非罗列的原因：① 控文档长度与 token 成本；② 摊平单条极端评价的噪声；
③ 让"口碑"成为一个可被稳定检索的语义单元。
"""
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from .. import config
from ..llm import get_llm
from ..prompts import REVIEW_SUMMARY_PROMPT

# 出口兜底：任何金额表达式都从聚合产物里抹掉。
# 为什么必须做：价格进向量库 = 快照过期 → 检索到旧价 → 助手复述旧价 = 幻觉事故。
_AMOUNT_RE = re.compile(
    r"(?:¥|￥|\$)\s*\d+(?:\.\d{1,2})?"
    r"|\d+(?:\.\d{1,2})?\s*(?:元|块钱|块|人民币)"
    r"|\d+(?:\.\d{1,2})?\s*(?:折|折起)"
)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)


def _est_tokens(s: str) -> float:
    """与 app/sessions.py 同口径的粗估：CJK 按 1 token/字，其余按 3.3 字符/token。

    不引入 tiktoken：这里只需要一个**保守的截断依据**，不需要精确计数。
    """
    cjk = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    return cjk + (len(s) - cjk) / 3.3


def _strip_amounts(s: str) -> str:
    if not isinstance(s, str):
        return ""
    out = _AMOUNT_RE.sub("", s)
    return re.sub(r"\s{2,}", " ", out).strip(" ，,、。;；")


def star_stats(reviews: list[dict]) -> dict:
    """星级统计（确定性的，不走 LLM）→ {starAvg, starDist, reviewCount}。"""
    n = len(reviews)
    dist = {str(i): 0 for i in range(1, 6)}
    total = 0
    for r in reviews:
        s = int(r.get("star") or 0)
        total += s
        if 1 <= s <= 5:
            dist[str(s)] += 1
    return {
        "starAvg": round(total / n, 1) if n else 0.0,
        "starDist": dist,
        "reviewCount": n,
    }


def _truncate(reviews: list[dict], budget: int) -> list[dict]:
    """按 token 预算截断：评价按时间倒序给，超预算就**丢最旧的**（保留最近的）。"""
    kept: list[dict] = []
    used = 0.0
    for r in reviews:
        line = f"- {r.get('star')}★ {r.get('content') or '（无文字）'}\n"
        cost = _est_tokens(line)
        if kept and used + cost > budget:
            break
        kept.append(r)
        used += cost
    return kept


def _parse(raw: str) -> dict:
    """把模型输出解析成固定 schema；任何异常都退化为空结果（不编造）。"""
    text = _JSON_FENCE_RE.sub("", (raw or "").strip()).strip()
    try:
        data = json.loads(text)
    except ValueError:
        # 容错：模型偶尔会在 JSON 前后带一句话，截取第一个 { 到最后一个 }
        i, j = text.find("{"), text.rfind("}")
        if i < 0 or j <= i:
            return {"pros": [], "cons": [], "quotes": [], "text": ""}
        try:
            data = json.loads(text[i:j + 1])
        except ValueError:
            return {"pros": [], "cons": [], "quotes": [], "text": ""}

    def arr(key: str, limit: int) -> list[str]:
        v = data.get(key)
        if not isinstance(v, list):
            return []
        out = [_strip_amounts(str(x)) for x in v]
        return [x for x in out if x][:limit]

    return {
        "pros": arr("pros", 3),
        "cons": arr("cons", 3),
        "quotes": arr("quotes", 2),
        "text": _strip_amounts(str(data.get("text") or "")),
    }


def aggregate_reviews(name: str, sub_title: str, reviews: list[dict]) -> dict:
    """评价列表 → {pros, cons, quotes, text}。

    reviews 每项需含 `star` 与 `content`（已由调用方过滤为 status=1）。
    无评价时直接返回空结果（不发请求，省一次 LLM 调用）。
    """
    if not reviews:
        return {"pros": [], "cons": [], "quotes": [], "text": ""}

    picked = _truncate(reviews, config.RAG_AGG_MAX_INPUT_TOKENS)
    stats = star_stats(picked)
    lines = [
        f"商品名称：{name}",
        f"商品卖点：{sub_title or '（无）'}",
        f"评价条数：{stats['reviewCount']}，平均 {stats['starAvg']} 分",
        "评价原文（星级 内容）：",
    ]
    for r in picked:
        content = (r.get("content") or "").strip()
        lines.append(f"- {r.get('star')}★ {content or '（无文字）'}")

    llm = get_llm(temperature=0)
    msg = llm.invoke([
        SystemMessage(content=REVIEW_SUMMARY_PROMPT),
        HumanMessage(content="\n".join(lines)),
    ])
    return _parse(getattr(msg, "content", "") or "")
