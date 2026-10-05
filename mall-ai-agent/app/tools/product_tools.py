"""商品相关工具：LLM 通过这些工具调用 mall-v2 portal 的真实接口。

docstring 就是写给 LLM 看的「工具说明书」——描述越详细，
LLM 越知道什么时候该调它、参数怎么填、返回什么字段。

接口口径（mall-v2）：
- 列表 `GET /product/list`：keyword/categoryId/brandId/pageNum(从 1)/pageSize。
  有 keyword 时后端走 ES（失败自动降级 DB LIKE）；无 keyword 时是分类/品牌浏览。
- 详情 `GET /product/{id}`：返回 `{product: ProductVO, skus: [Sku]}`。
  **mall-v2 没有属性表**，因此没有参数列表（productAttributeList）。
"""
import json

from langchain_core.tools import tool

from . import mall_client
from .. import config


def _extract_list(data: dict) -> list:
    """分页接口统一返回 {code, message, data:{list:[...], total,...}}"""
    d = data.get("data") or {}
    return d.get("list") or []


def normalize_product(p: dict | None) -> dict:
    """把 ProductVO 归一成助手内部统一的商品字典。

    关键：SPU 表不存售价，售价在 SKU 表，列表/详情返回的是 **SKU 最低价**，
    字段名是 `lowestPrice`；这里统一改名成 `price`，让下游（卡片、提示词）只需认一个字段。
    """
    p = p or {}
    return {
        "id": p.get("id"),
        "name": p.get("name") or "",
        "pic": p.get("pic") or "",          # 商品主图（product.pic）
        "price": p.get("lowestPrice"),      # SKU 最低价，单位元
        "productSn": p.get("productSn") or "",
        "sale": p.get("sale"),
        "status": p.get("status"),
    }


@tool
def search_products(keyword: str, category_id: int | None = None, brand_id: int | None = None) -> str:
    """按关键词搜索商品，返回商品列表（JSON 字符串）。

    使用场景：用户想找某类商品，例如「帮我找小米手机」「2000元以下有什么手机」「有哪些充电宝」。
    参数 keyword 是搜索关键词，直接取用户提到的商品类别或品牌；不要传空串。
    category_id / brand_id 可选，仅当用户明确指定分类或品牌时才传。
    返回每个商品的字段：id（商品id）、name（名称）、price（价格，单位元，即该商品 SKU 最低价）、
    pic（主图）、sale（销量）、status（上下架）。
    有搜索词时后端走 Elasticsearch 相关度检索，异常自动降级为名称模糊查询，无需你处理。
    分页从第 1 页开始（最多返回 10 条）。
    用户如果提到价格条件，先调用本工具拿到结果，再根据 price 字段自行筛选，
    严禁编造不存在的商品或价格。
    """
    params = {"keyword": keyword, "pageNum": 1, "pageSize": 10}
    if category_id:
        params["categoryId"] = category_id
    if brand_id:
        params["brandId"] = brand_id
    data = mall_client.api_get(config.PORTAL_BASE_URL, "/product/list", params=params)
    items = [normalize_product(p) for p in _extract_list(data)]
    return json.dumps(items, ensure_ascii=False)


@tool
def show_products(product_ids: str) -> str:
    """把符合用户条件的商品以卡片形式展示给用户（展示在回复消息下方）。

    使用场景：每次调用 search_products（或 recommend_for_me）拿到结果后，必须调用本工具，
    传入符合用户要求的商品 id（JSON 数组字符串，如 "[28, 27]"）。
    规则：
    - id 只能取自 search_products / recommend_for_me 返回结果里的 id 字段，严禁编造 id
    - 只传真正符合用户条件的商品；不符合的不要传
    - 如果没有一个商品符合条件，就不要调用本工具，直接告诉用户没有找到
    卡片上会展示这些商品的图片、名称、价格，用户可点击查看详情。
    """
    return product_ids


@tool
def get_product_detail(product_id: int) -> str:
    """查询单个商品的详情，返回详情 JSON 字符串。

    使用场景：用户已锁定某个商品，想进一步了解规格、价格、库存。
    参数 product_id 必须是 search_products / 商品卡片返回的 id 字段值。
    返回结构：{"product": {...}, "skus": [ {...}, ... ]}。
    - product：商品基本信息，含 id、name、pic（主图）、price（SKU 最低价）
    - skus：可选规格列表，每个 SKU 含 id（下单/加购要用它）、skuCode、spData（规格 JSON，
      展示用）、price（单价）、stock（库存）、pic（可为空，为空时展示商品主图）
    注意：mall-v2 暂无商品参数表，返回里没有属性列表，不要向用户承诺参数级细节。
    """
    data = mall_client.api_get(config.PORTAL_BASE_URL, f"/product/{product_id}")
    vo = data.get("data") or {}
    product = normalize_product(vo.get("product"))
    skus = vo.get("skus") or []
    return json.dumps({"product": product, "skus": skus}, ensure_ascii=False)
