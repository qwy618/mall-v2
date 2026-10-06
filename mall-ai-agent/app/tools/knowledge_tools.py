"""知识检索工具：把「语义道」（向量检索）暴露给 LLM。

**为什么单独一个工具而不是塞进 search_products**：
结构类（价格/库存/规格）必须实时查 portal，语义类（口碑/体验/适用场景）来自
预建索引 —— 两者的**时效性与可信来源完全不同**，混在一个工具里会让模型
把"索引里的旧信息"当"实时事实"用。分开后，路由（D5-5）由 LLM 依 docstring 决定，
并用 SYSTEM_PROMPT 规则显式划界兜底。

返回给 LLM 的 JSON **不含 score**（内部诊断量，不进上下文、更不给用户）；
`snippet` 已在聚合层做过金额清洗（§4.4），这里再兜一次超长截断。
"""
import json

from langchain_core.tools import tool

from ..rag import retriever


@tool
def search_knowledge(query: str, product_ids: str = "", category_id: int | None = None) -> str:
    """检索商品的「档案」与「已审核评价的聚合口碑」，回答主管感受与使用体验类问题。

    使用场景：用户询问商品的使用体验、口碑、优缺点、手感、适合什么人、真实反馈，
    例如「小米12 Pro 用起来怎么样」「有没有好评多一点的手机」「这个笔记本有什么槽点」
    「这款冰箱噪音大吗 用着怎么样」。
    参数 query：把用户的主观问题改写成一句检索式（如「屏幕 续航 发热 体验」）。
    参数 product_ids：可选，JSON 数组字符串（如 "[40,37]"）。
      当先用 search_products 按价格/分类筛出候选后，再把候选 id 传进来做口碑对比。
    参数 category_id：可选，限定分类，减少跨品类误召回。

    返回 JSON：{"hit": bool, "items":[{productId, name, docType, snippet, starAvg, reviewCount}]}

    重要边界（务必遵守）：
    - 本工具**只**用于主观/体验类信息。
    - **价格、库存、是否有货、规格参数一律不要用本工具回答**，必须改用
      search_products / get_product_detail —— 本工具的返回里**没有也不许推断**价格与库存。
    - 若 hit 为 false 或 items 为空，必须如实告知用户没有可靠信息，严禁用常识补充。
    - 引用时说明信息来自哪些商品（用商品名称，不要输出商品 id、docType 等内部标识）。
    """
    ids: list[int] | None = None
    raw = (product_ids or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                ids = [int(x) for x in parsed if str(x).strip().lstrip("-").isdigit()]
        except (ValueError, TypeError):
            ids = None          # 参数不合法就当没传，而不是让整个检索失败

    res = retriever.search_knowledge_impl(query, product_ids=ids, category_id=category_id)

    # 🔴 hit=false（L1 闸门拦下）时**绝不把低于阈值的候选透给 LLM**：
    #    那不是"信息"，是"最像的噪声"。透出去等于给模型递了编造素材，
    #    与"没有可靠信息就如实拒答"直接矛盾。retriever 内部保留 items 仅供诊断/标定。
    ok = bool(res.get("hit"))
    raw_items = (res.get("items") or []) if ok else []

    # 只把「能给用户看」的字段回给 LLM：剔除 score 等内部标识
    items = [
        {
            "productId": it.get("productId"),
            "name": it.get("name") or "",
            "docType": it.get("docType") or "",
            "snippet": it.get("snippet") or "",
            **({"starAvg": it["starAvg"], "reviewCount": it["reviewCount"]}
               if "starAvg" in it else {}),
        }
        for it in raw_items
    ]
    return json.dumps({"hit": ok and bool(items), "items": items},
                      ensure_ascii=False)
