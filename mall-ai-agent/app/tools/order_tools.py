"""电商闭环工具：加购、生成确认单、真正下单。

安全铁律：place_order 只有在用户点击「确认下单」按钮（前端发来系统指令）后，
LLM 才会调用；草稿机制保证下单参数来自 preview_order 的产物，LLM 无法编造。
token 通过 ContextVar 从请求上下文透传（JWT 透传），工具不接收 token 参数。

mall-v2 下单链路（债务 23 幂等）：
    POST /order/token   → 取一次性令牌（TTL 900s）
    POST /order/create  → 带 submitToken，缺了会直接失败
"""
import json
from contextvars import ContextVar

from langchain_core.tools import ToolException, tool

from . import mall_client
from .mall_client import NeedLoginError
from .. import config, orders

# 请求上下文：main.py 在调用 agent 前设置，工具从这里拿当前会话的 token/session/member
current_token: ContextVar[str | None] = ContextVar("agent_token", default=None)
current_session: ContextVar[str | None] = ContextVar("agent_session", default=None)
current_member: ContextVar[int | None] = ContextVar("agent_member", default=None)


def _require_token() -> str:
    token = current_token.get()
    if not token:
        raise NeedLoginError("用户未登录")
    return token


def fetch_cart(token: str) -> list:
    """拉取当前会员购物车原始条目列表（CartItemVO）。

    注意 mall-v2 的字段名：条目标识是 `cartItemId`，规格是 `skuId`（不是 id/productSkuId）。
    """
    data = mall_client.api_get(config.PORTAL_BASE_URL, "/cart/list", token=token)
    return data.get("data") or []


def find_cart_item(token: str, *, cart_item_id: int | None = None,
                   product_id: int | None = None, sku_id: int | None = None) -> dict | None:
    """在购物车里定位条目：给了 cartItemId 就按它找，否则按 (productId, skuId) 找。"""
    for it in fetch_cart(token):
        if cart_item_id is not None:
            if it.get("cartItemId") == cart_item_id:
                return it
        elif product_id is not None and it.get("productId") == product_id and it.get("skuId") == sku_id:
            return it
    return None


@tool
def list_cart() -> str:
    """查看当前购物车（需要用户已登录），返回条目 JSON 数组。

    使用场景：用户问「我购物车有什么」「看看我的购物车」，或需要拿到 cartId 时。
    返回每项字段：cartId（购物车条目id）、skuId（规格id）、productId（商品id）、
    productName、pic、price（实时单价）、quantity、checked（1选中/0未选）、offline（true=已下架不可结算）。
    """
    token = _require_token()
    items = []
    for it in fetch_cart(token):
        items.append({
            "cartId": it.get("cartItemId"),
            "skuId": it.get("skuId"),
            "productId": it.get("productId"),
            "productName": it.get("productName") or "",
            "pic": it.get("pic") or "",
            "price": it.get("price"),
            "quantity": it.get("quantity"),
            "checked": it.get("checked"),
            "offline": bool(it.get("offline")),
        })
    return json.dumps(items, ensure_ascii=False)


@tool
def add_to_cart(product_id: int, quantity: int) -> str:
    """把商品加入购物车（需要用户已登录）。

    使用场景：用户明确说「加入购物车」「帮我买XX」「买一个XX」。
    参数 product_id 必须来自 search_products / 商品卡片里的 id；
    quantity 是购买数量——必须来自用户明确说的数字；用户没说数量时必须先询问，
    严禁自作主张按全部库存下单。
    执行流程：先查商品详情拿一个**有库存的 SKU**（用户未指定规格时默认取有库存里
    **价格最低**的那个，可预期且对用户友好），校验数量不超过库存，
    再调 POST /cart/add?skuId=&quantity=，最后从购物车列表按 (productId, skuId) 匹配，
    返回 cartId——后续 preview_order 要用这个 cartId。
    返回 JSON：{"cartId": 购物车条目id, "productName": 商品名, "price": 实时单价,
    "quantity": 数量, "spec": 所选规格（spData 原样，展示用）}
    注意：图片、名称等快照由后端自动落库，你不传也不该传。
    """
    token = _require_token()
    detail = mall_client.api_get(config.PORTAL_BASE_URL, f"/product/{product_id}", token=token)
    vo = detail.get("data") or {}
    product = vo.get("product") or {}
    if not product or not product.get("id"):
        raise ToolException(f"商品 {product_id} 不存在")
    skus = vo.get("skus") or []
    in_stock = [s for s in skus if (s.get("stock") or 0) > 0]
    if not in_stock:
        raise ToolException(f"商品「{product.get('name')}」已无库存")
    sku = min(in_stock, key=lambda s: float(s.get("price") or 0))
    stock = int(sku.get("stock") or 0)
    # 数量红线：用户没说数量时 LLM 必须先问（见 SYSTEM_PROMPT 规则 12）；
    # 这里兜底拦截「数量 > 库存」的越界调用，报错时带上真实库存数
    if quantity <= 0:
        raise ToolException("购买数量必须是大于 0 的整数")
    if quantity > stock:
        raise ToolException(f"库存不足：商品「{product.get('name')}」目前只有 {stock} 件，请减少数量")

    # mall-v2 是 @RequestParam，图/名称等快照由后端落库
    mall_client.api_post(config.PORTAL_BASE_URL, "/cart/add",
                         params={"skuId": sku["id"], "quantity": quantity}, token=token)

    it = find_cart_item(token, product_id=product_id, sku_id=sku["id"])
    if not it:
        raise ToolException("加入购物车后未在购物车列表中找到该商品，请重试")
    return json.dumps({
        "cartId": it.get("cartItemId"),
        "productName": it.get("productName") or product.get("name") or "",
        "price": it.get("price"),
        "quantity": it.get("quantity") or quantity,
        "spec": sku.get("spData") or "",
    }, ensure_ascii=False)


@tool
def preview_order(cart_id: int) -> str:
    """生成订单确认单（需要用户已登录）。这一步只算价格、不真正下单。

    使用场景：用户说「帮我下单」「结算」时，先把 add_to_cart 返回的 cartId 传进来。
    系统会根据返回结果生成订单草稿并以确认卡片展示给用户，你必须停下来
    告诉用户「请核对订单信息，点击确认下单按钮」，绝不能直接调用 place_order。
    返回 JSON 含：收货地址列表（memberReceiveAddressList）、商品清单（cartPromotionItemList）、
    金额明细 calcAmount（totalAmount / promotionAmount / couponAmount / integrationAmount / payAmount）。
    金额由后端 `POST /order/preview` 计算——**与真正下单 /order/create 是同一段代码**，
    含会员折扣/优惠券/积分抵扣，因此卡片金额与最终下单金额逐分一致，请如实向用户展示。
    """
    token = _require_token()
    it = find_cart_item(token, cart_item_id=cart_id)
    if not it:
        raise ToolException(f"购物车条目 {cart_id} 不存在，请先加入购物车")
    if it.get("offline"):
        raise ToolException("该商品已下架，无法结算")

    # 与下单同源的试算：不扣库存、不落库、不消耗令牌（addressId 省略 → 后端取默认地址）
    body = {
        "items": [{
            "skuId": it.get("skuId"),
            "quantity": it.get("quantity") or 1,
            "cartItemId": cart_id,
        }],
        "useIntegration": 0,
    }
    data = mall_client.api_post(config.PORTAL_BASE_URL, "/order/preview",
                                body=body, token=token).get("data") or {}
    addr = data.get("address")
    if not addr:
        raise ToolException("您还没有收货地址，请先到个人中心添加收货地址")

    rows = data.get("items") or []
    result = {
        "cartPromotionItemList": [{
            "id": cart_id,
            "productId": r.get("productId"),
            "skuId": r.get("skuId"),
            "productName": r.get("productName") or "",
            "productPic": r.get("productPic") or "",
            "spData": r.get("spData") or "",
            "price": r.get("price"),
            "quantity": r.get("quantity"),
            "realAmount": r.get("realAmount"),
            "promotionMessage": "",
        } for r in rows],
        "memberReceiveAddressList": [addr],
        "calcAmount": {
            "totalAmount": data.get("totalAmount"),
            "promotionAmount": data.get("promotionAmount"),
            "couponAmount": data.get("couponAmount"),
            "integrationAmount": data.get("integrationAmount"),
            "useIntegration": data.get("useIntegration") or 0,
            "payAmount": data.get("payAmount"),
        },
        "levelName": data.get("levelName"),
    }
    return json.dumps(result, ensure_ascii=False)


@tool
def place_order(draft_id: str) -> str:
    """真正下单（需要用户已登录，且用户已点击「确认下单」按钮）。

    只有收到系统消息「【系统指令】用户已确认下单，draft_id=xxx」时才能调用本工具，
    draft_id 必须原样取自该系统消息，严禁自己编造。
    下单参数（购物车条目、收货地址）取自 preview_order 生成的草稿，你无法也不应修改。
    幂等说明：同一 draft_id 重复调用是安全的——若这份草稿已经下过单，会直接返回
    首次的下单结果（网络重试不会产生第二单），你不要据此向用户强调"重复下单"。
    返回 JSON 含：id、订单号 orderSn、应付金额 payAmount。
    """
    token = _require_token()
    session_id = current_session.get() or ""
    member_id = current_member.get()

    # ① 结果回放（M1 幂等第 2 层）：这份草稿若已成功下单，直接返回首次结果。
    #    必须先于消费草稿判断——否则重试会先撞"草稿不存在"，把成功误报成失败。
    replayed = orders.recall_result(draft_id)
    if replayed:
        return _order_result(token, replayed)

    # ② 原子消费草稿（第 1 层）：并发/连点只有一个能拿到，其余得到 None
    draft = orders.pop_draft(session_id, member_id, draft_id)
    if not draft:
        raise ToolException("订单信息已过期，请重新确认订单")

    it = find_cart_item(token, cart_item_id=draft["cart_id"])
    if not it:
        raise ToolException("购物车条目已失效，请重新确认订单")

    # ③ 取一次性幂等令牌（债务 23）。取令牌与用令牌必须紧邻，中间不要插别的工具调用
    tk = mall_client.api_post(config.PORTAL_BASE_URL, "/order/token", token=token).get("data")
    if not tk:
        raise ToolException("获取下单令牌失败，请稍后重试")

    # ④ 提交下单（必带 submitToken，否则被后端拒绝；DB 唯一键是第 3 层兜底）
    body = {
        "addressId": draft["address_id"],
        "items": [{
            "skuId": it.get("skuId"),
            "quantity": it.get("quantity"),
            "cartItemId": it.get("cartItemId"),
        }],
        "submitToken": tk,
        "useIntegration": draft.get("use_integration") or 0,
    }
    res = mall_client.api_post(config.PORTAL_BASE_URL, "/order/create", body=body, token=token)
    order_id = res.get("data")
    if not order_id:
        raise ToolException(f"下单失败：{res.get('message')}")

    orders.remember_result(draft_id, order_id)   # 记结果，供重试回放
    return _order_result(token, order_id)


def _order_result(token: str, order_id) -> str:
    """按 orderId 组装统一下单结果（首次下单与回放共用，保证两种路径输出一致）。"""
    detail = mall_client.api_get(config.PORTAL_BASE_URL, "/order/detail",
                                 params={"orderId": order_id}, token=token)
    order = (detail.get("data") or {}).get("order") or {}
    return json.dumps({
        "id": order.get("id") or order_id,
        "orderSn": order.get("orderSn"),
        "payAmount": order.get("payAmount"),
    }, ensure_ascii=False)
