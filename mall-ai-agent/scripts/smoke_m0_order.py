"""M0 补验：下单这一公里（place_order → /order/token + /order/create）。

运行：.venv\\Scripts\\python scripts/smoke_m0_order.py
前置：mall-portal 已在 8081 运行。

说明：验证 place_order 两段式（/order/token → /order/create 带 submitToken）真实可用，
并回归「下单清车后 /cart/list 不得残留已下单条目」这一购物车缓存失效缺陷（B1）。
跑完会自动取消订单，不留脏数据。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import orders  # noqa: E402
from app.tools import mall_client  # noqa: E402
from app.tools.order_tools import (  # noqa: E402
    current_session, current_token, add_to_cart, fetch_cart, place_order)
from app.tools.product_tools import get_product_detail, search_products  # noqa: E402

PHONE = "13900007777"
PASSWORD = "Test123456"
SESSION = "smoke-m0-order"
P = mall_client.config.PORTAL_BASE_URL

ok = 0
fail = 0


def check(label, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {label} {extra}")
    else:
        fail += 1
        print(f"  [FAIL] {label} {extra}")


def main():
    print("=== M0 补验：下单链路 ===\n")
    mall_client.api_post(P, "/member/login", params={"phone": PHONE, "password": PASSWORD})
    login = mall_client.api_post(P, "/member/login", params={"phone": PHONE, "password": PASSWORD})
    token = (login.get("data") or {}).get("token")
    check("登录", bool(token))
    if not token:
        sys.exit(1)
    current_token.set(token)
    current_session.set(SESSION)

    # 清空购物车，挑一个有库存的商品加购
    for it in fetch_cart(token):
        try:
            mall_client.api_delete(P, "/cart/delete", params={"cartItemId": it["cartItemId"]}, token=token)
        except Exception:  # noqa: BLE001 —— 并发/已消费时忽略
            pass
    items = json.loads(search_products.invoke({"keyword": "手机"}))
    target = None
    for it in items:
        vo = json.loads(get_product_detail.invoke({"product_id": it["id"]}))
        if any((s.get("stock") or 0) > 0 for s in (vo.get("skus") or [])):
            target = it
            break
    check("挑到有库存商品", target is not None)
    if not target:
        sys.exit(1)
    added = json.loads(add_to_cart.invoke({"product_id": target["id"], "quantity": 1}))
    cart_id = added.get("cartId")

    addrs = mall_client.api_get(P, "/member/address/list", token=token).get("data") or []
    check("有收货地址", len(addrs) > 0)
    if not addrs:
        sys.exit(1)
    addr_id = addrs[0]["id"]

    # 手工造草稿（模拟 main.py 的 _build_confirm 产物）
    draft_id = orders.create_draft(SESSION, {"cart_id": cart_id, "address_id": addr_id,
                                             "pay_amount": added.get("price")})
    order = json.loads(place_order.invoke({"draft_id": draft_id}))
    check("下单成功拿到订单号", bool(order.get("orderSn")),
          f"orderSn={order.get('orderSn')} payAmount={order.get('payAmount')}")
    after = fetch_cart(token)
    mine = [c for c in after if c.get("cartItemId") == cart_id]
    # 回归：下单清车后 /cart/list 必须立即不含该条目（B1 —— OrderServiceImpl 清车后需失效购物车缓存）
    check("购物车条目已消费（缓存随下单失效，无幽灵条目）", not mine,
          f"残留={[(c.get('cartItemId'), c.get('productName')) for c in mine]}")
    check("草稿一次性销毁", orders.get_draft(SESSION, draft_id) is None)

    # 清理：取消本脚本产生的所有待付款订单（含上次客户端超时但服务端已成功的）
    pending = mall_client.api_get(P, "/order/list",
                                  params={"status": 0, "pageNum": 1, "pageSize": 50},
                                  token=token).get("data") or {}
    for o in (pending.get("list") or []):
        try:
            mall_client.api_post(P, "/order/cancel", params={"orderId": o["id"]}, token=token)
            print(f"  （已取消待付款订单 {o.get('orderSn')}）")
        except Exception as e:  # noqa: BLE001
            print(f"  （取消失败，请手工清理 {o.get('orderSn')}: {e}）")

    print(f"\n=== 结果：{ok} 通过 / {fail} 失败 ===")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
