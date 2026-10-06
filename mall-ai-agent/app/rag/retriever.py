"""检索：语义问题 → 向量召回 → 去重 → 阈值闸门 → 供工具返回的结构化结果。

**只在"语义道"里说话**：本模块返回的内容永远不含价格/库存（索引时已排除，
这里也不做任何数值推断）。价格类问题应由 search_products / get_product_detail
回答 —— 路由由 LLM 依工具 docstring 决定，并用 SYSTEM_PROMPT 规则兜底。

拒答是**两级**的（docs/M3 §6.3）：
  L1 本模块：无结果 或 maxScore < RAG_SIM_THRESHOLD → hit=false（不进 LLM）；
  L2 工具/提示词层：有结果但 LLM 自评"不足以回答" → 输出固定哨兵，后处理转拒答话术。
单靠阈值在小数据量下不可靠，所以才要第二级。
"""
from __future__ import annotations

import logging

from .. import config
from . import embedder, vector_store

log = logging.getLogger(__name__)

# 两类文档都参与召回；snippet 截断到可读长度（不向用户暴露完整 payload）
_SNIPPET_MAX = 300


def _snippet(payload: dict) -> str:
    text = (payload or {}).get("text") or ""
    text = " ".join(str(text).split())
    return text[:_SNIPPET_MAX] + ("…" if len(text) > _SNIPPET_MAX else "")


def _to_item(hit: dict) -> dict:
    p = hit.get("payload") or {}
    item = {
        "productId": int(p.get("productId") or 0),
        "name": p.get("name") or "",
        "docType": p.get("docType") or "",
        "snippet": _snippet(p),
        "score": round(float(hit.get("score") or 0.0), 4),
    }
    # 口碑文档才有星级/条数；商品档案没有就当 0
    if p.get("docType") == "review_summary":
        item["starAvg"] = round(float(p.get("starAvg") or 0.0), 1)
        item["reviewCount"] = int(p.get("reviewCount") or 0)
    return item


def search_knowledge_impl(query: str,
                          product_ids: list[int] | None = None,
                          category_id: int | None = None,
                          top_k: int | None = None) -> dict:
    """检索入口。返回：

    {
      "hit": bool,                # 是否检到可信信息（L1 闸门结果）
      "maxScore": float,          # 最高相似度（用于诊断/标定）
      "threshold": float,         # 当前阈值（诊断）
      "items": [ {productId, name, docType, snippet, score[, starAvg, reviewCount]} ],
      "reason": str               # hit=false 时的原因（disabled/empty/低于阈值）
    }

    永不抛异常：检索失败等价于"没有可靠信息"，让助手如实拒答，
    而不是把 Qdrant 的连接错误糊到用户脸上。
    """
    k = top_k or config.RAG_TOP_K
    empty = {"hit": False, "maxScore": 0.0,
             "threshold": config.RAG_SIM_THRESHOLD, "items": []}

    q = (query or "").strip()
    if not q:
        return {**empty, "reason": "empty_query"}

    if not config.RAG_ENABLED:
        # 一键回退：索引有问题时置 0，助手直接说"暂无信息"，其余工具不受影响
        return {**empty, "reason": "disabled"}

    try:
        vec = embedder.embed_query(q)
        hits = vector_store.search(
            vec,
            limit=max(k * config.RAG_FETCH_MULTIPLIER, k),
            doc_types=["product_profile", "review_summary"],
            product_ids=product_ids,
            category_id=category_id,
        )
    except Exception as e:  # noqa: BLE001 —— 检索故障 = 没有可靠信息
        log.warning("RAG 检索失败：%s", e)
        return {**empty, "reason": f"error: {e}"}

    if not hits:
        return {**empty, "reason": "no_result"}

    # 同商品去重：一个商品最多保留 RAG_MAX_PER_PRODUCT 条（默认 1 条，取最高分）
    #   命中已按分数降序，所以同一 productId 第一次出现就是最高分那条
    per_product: dict[int, int] = {}
    deduped: list[dict] = []
    for h in hits:
        pid = int((h.get("payload") or {}).get("productId") or 0)
        cnt = per_product.get(pid, 0)
        if cnt >= config.RAG_MAX_PER_PRODUCT:
            continue
        per_product[pid] = cnt + 1
        deduped.append(h)

    max_score = max(float(h.get("score") or 0.0) for h in hits)
    items = [ _to_item(h) for h in deduped[:k] ]

    # L1 闸门：最高分（用的是全量命中，不是去重后）低于阈值 → 拒答
    # 注意：这里仍回带 items **仅供诊断/标定**（看"最像的是什么、差多少"）；
    # 调用方（knowledge_tools）必须在 hit=false 时丢弃 items，不得透给 LLM。
    if max_score < config.RAG_SIM_THRESHOLD:
        return {**empty, "maxScore": round(max_score, 4),
                "items": items, "reason": "below_threshold"}

    return {
        "hit": True,
        "maxScore": round(max_score, 4),
        "threshold": config.RAG_SIM_THRESHOLD,
        "items": items,
        "reason": "",
    }
