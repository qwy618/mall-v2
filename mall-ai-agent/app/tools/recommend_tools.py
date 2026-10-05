"""猜你喜欢：基于用户真实行为数据做个性化推荐。

数据来源（全部走 portal REST，token 由 ContextVar 透传）：
- 购物车 `GET /cart/list`（条目自带 productId）
- 收藏   `GET /member/collect/list`

召回用 `GET /product/similar/{id}`：同分类、已上架、排除自身、按销量倒序，
天然是「和你买过/收藏过的同类商品」。mall-v2 没有浏览历史接口，
也没有把类目 id 暴露给 C 端，所以这里不按类目聚合，而是直接用相似商品召回。

推荐结果仍走 show_products 过滤链路展示成卡片 —— LLM 编造不出推荐商品。
"""
import json

from langchain_core.tools import tool

from . import mall_client
from .. import config
from .order_tools import fetch_cart, _require_token
from .product_tools import normalize_product

MAX_RECOMMEND = 6   # 最多推荐商品数
MAX_SEEDS = 4       # 最多用几个「种子商品」去召回


def _similar(token: str, product_id) -> list:
    """取某商品的相似商品（同分类热销）；失败就当这个种子没有召回，不影响整体。"""
    try:
        data = mall_client.api_get(config.PORTAL_BASE_URL, f"/product/similar/{product_id}",
                                   params={"pageSize": 6}, token=token)
        return data.get("data") or []
    except Exception:
        return []


@tool
def recommend_for_me() -> str:
    """「猜你喜欢」：根据用户的历史行为（购物车、收藏）推荐用户可能喜欢的商品。

    使用场景：用户说「猜猜我喜欢什么」「给我推荐点东西」「有什么适合我的」之类，
    想要个性化推荐时必须调用本工具，不要用 search_products 代替。
    返回 JSON 数组，每个元素含：id（商品id）、name、price、pic、reason（推荐理由，
    如"你买过同类商品"）。
    返回空数组 [] 表示用户还没有任何行为数据（购物车和收藏都为空），
    此时如实告诉用户「还没有你的喜好数据，先去逛逛或收藏喜欢的商品，我就能猜你的心思啦」，
    不要凭空编造推荐、不要调用其他工具兜底推荐。
    拿到返回结果后，必须调用 show_products 把这些商品 id 展示成卡片（id 只能来自本工具返回结果）。
    """
    token = _require_token()

    cart_items = fetch_cart(token)
    collections = mall_client.api_get(config.PORTAL_BASE_URL, "/member/collect/list",
                                     token=token).get("data") or []

    # 1. 种子商品：购物车优先（更强的购买意向），再收藏
    seeds: list[tuple] = []
    for it in cart_items:
        if it.get("productId"):
            seeds.append((it["productId"], "你买过同类商品"))
    for c in collections:
        if c.get("productId"):
            seeds.append((c["productId"], "你收藏过同类商品"))
    if not seeds:
        return "[]"

    # 2. 逐种子召回相似商品，排除购物车里已有的、以及重复的
    owned = {it.get("productId") for it in cart_items}
    seen: set = set()
    recs: list = []
    for pid, reason in seeds[:MAX_SEEDS]:
        for it in _similar(token, pid):
            rp = normalize_product(it)
            if not rp.get("id") or rp["id"] in owned or rp["id"] in seen:
                continue
            seen.add(rp["id"])
            recs.append({**rp, "reason": reason})
            if len(recs) >= MAX_RECOMMEND:
                break
        if len(recs) >= MAX_RECOMMEND:
            break
    return json.dumps(recs, ensure_ascii=False)
