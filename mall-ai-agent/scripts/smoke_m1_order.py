"""M1 验收（下单链路）：两段式下单 + **结果回放幂等** + 草稿原子消费 + B1 缓存失效回归。

与 M0 的区别：M0 只验「能下单」，这里额外验 M1 新增的幂等语义
——同一份草稿重复 place_order 必须**返回同一笔订单**，不产生第二单。

走的是生产同一条路径：preview_order → main._build_confirm（真实建草稿）→ place_order。
不需要 LLM，所以不依赖 DEEPSEEK_API_KEY。

运行：.venv\\Scripts\\python scripts/smoke_m1_order.py
跑完自动取消测试订单、清理购物车。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config, main, orders, store  # noqa: E402
from app.tools import mall_client  # noqa: E402
from app.tools.order_tools import (  # noqa: E402
    add_to_cart, current_member, current_session, current_token,
    list_cart, place_order, preview_order, fetch_cart)

PHONE = "13900007777"
PASSWORD = "Test123456"
SESSION = "smoke-m1-order"

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


def login() -> str:
    res = mall_client.api_post(config.PORTAL_BASE_URL, "/member/login",
                               params={"phone": PHONE, "password": PASSWORD})
    return (res.get("data") or {}).get("token")


def pick_in_stock():
    lst = mall_client.api_get(config.PORTAL_BASE_URL, "/product/list",
                              params={"pageNum": 1, "pageSize": 10})
    for p in (lst.get("data") or {}).get("list", []):
        d = mall_client.api_get(config.PORTAL_BASE_URL, f"/product/{p['id']}")
        vo = d.get("data") or {}
        for s in vo.get("skus") or []:
            if (s.get("stock") or 0) > 0:
                return vo.get("product"), s
    return None, None


def main_run() -> None:
    store.assert_available()
    print("=== M1 验收：下单链路 + 结果回放幂等 ===")

    token = login()
    check("登录", bool(token))
    member_id = mall_client.resolve_member_id(token)
    check("解析出 memberId（会话/草稿归属用）", member_id is not None, f"memberId={member_id}")

    current_token.set(token)
    current_session.set(SESSION)
    current_member.set(member_id)

    # 清理：购物车 + 旧会话状态
    for it in fetch_cart(token):
        try:
            mall_client.api_delete(config.PORTAL_BASE_URL, "/cart/delete",
                                   params={"cartItemId": it["cartItemId"]}, token=token)
        except Exception:  # noqa: BLE001
            pass
    store.clear_session(SESSION)

    product, sku = pick_in_stock()
    check("挑到有库存商品", product is not None,
          f"{product.get('name') if product else '-'}")

    added = json.loads(add_to_cart.invoke({"product_id": product["id"], "quantity": 1}))
    cart_id = added["cartId"]
    check("加购成功", bool(cart_id), f"cartId={cart_id}")

    # ---- 建草稿：走生产的 _build_confirm，而不是手工造 ----
    pv = json.loads(preview_order.invoke({"cart_id": cart_id}))
    confirm = main._build_confirm(SESSION, member_id, json.dumps(pv, ensure_ascii=False))
    check("生成确认单草稿", bool(confirm and confirm.get("draftId")),
          f"draftId={confirm.get('draftId') if confirm else None} payAmount={confirm.get('payAmount') if confirm else None}")
    draft_id = confirm["draftId"]

    # ---- 下单（第 1 次）----
    r1 = json.loads(place_order.invoke({"draft_id": draft_id}))
    order_id = r1.get("id")
    check("首次下单成功", bool(order_id), f"orderSn={r1.get('orderSn')} payAmount={r1.get('payAmount')}")

    # ---- 幂等：草稿已被原子消费 ----
    check("草稿已被消费（不可二次读取）",
          store.get_draft(SESSION, member_id, draft_id) is None)

    # ---- 幂等：重复 place_order 返回同一笔（结果回放）----
    r2 = json.loads(place_order.invoke({"draft_id": draft_id}))
    check("重复 place_order 返回同一 orderId（不产生第二单）",
          r2.get("id") == order_id, f"{order_id} vs {r2.get('id')}")
    check("回放的订单号/金额与首次一致",
          r2.get("orderSn") == r1.get("orderSn") and r2.get("payAmount") == r1.get("payAmount"))

    # ---- B1 缓存失效回归：下单后购物车不含该条目 ----
    left = [c for c in fetch_cart(token) if c.get("cartItemId") == cart_id]
    check("下单后购物车条目已消失（B1 缓存失效未回归）", not left,
          f"残留={left}")

    # ---- 清理：取消测试订单 ----
    try:
        mall_client.api_post(config.PORTAL_BASE_URL, "/order/cancel",
                            params={"orderId": order_id}, token=token)
        print(f"  （已取消测试订单 {r1.get('orderSn')}）")
    except Exception as e:  # noqa: BLE001
        print(f"  （取消失败，请手工清理：{e}）")
    store.clear_session(SESSION)


if __name__ == "__main__":
    try:
        main_run()
    finally:
        print(f"\n=== 结果：{PASS} 通过 / {FAIL} 失败 ===")
    sys.exit(1 if FAIL else 0)
