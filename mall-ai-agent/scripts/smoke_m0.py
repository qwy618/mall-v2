"""M0 验收脚本：直接调用工具层（不经过 LLM），验证与 mall-v2 真实接口的对接。

运行：.venv\\Scripts\\python scripts/smoke_m0.py
前置：mall-portal 已在 8081 运行。

验收点：
  1. search_products  → GET /product/list（真实商品、有价）
  2. get_product_detail → GET /product/{id}（product + skus）
  3. 未登录调 list_cart → 抛 NeedLoginError（验证 401 判定没坏）
  4. 登录后 add_to_cart → POST /cart/add?skuId=&quantity=，返回 cartId
  5. list_cart / preview_order 复述同一个 cartId
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tools import mall_client  # noqa: E402
from app.tools.mall_client import NeedLoginError  # noqa: E402
from app.tools.order_tools import (  # noqa: E402
    current_token, list_cart, add_to_cart, preview_order, fetch_cart)
from app.tools.product_tools import search_products, get_product_detail  # noqa: E402

# 测试会员（本地联调用；仅在脚本内出现，不要写进命令行）
PHONE = "13900007777"
PASSWORD = "Test123456"

ok = 0
fail = 0


def check(label: str, cond: bool, extra: str = ""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {label} {extra}")
    else:
        fail += 1
        print(f"  [FAIL] {label} {extra}")


def main():
    print("=== M0 工具层对接验收 ===\n")

    # 1. 搜索
    print("[1] search_products('手机')")
    items = json.loads(search_products.invoke({"keyword": "手机"}))
    check("返回非空列表", len(items) > 0, f"共 {len(items)} 条")
    check("含 id/name/price", bool(items and items[0].get("id") and items[0].get("price")),
          f"样例={items[0].get('name','')[:18]}... 价={items[0].get('price')}")

    # 2. 详情：挑一个有库存的 SKU
    print("\n[2] get_product_detail（找一个有库存的商品）")
    picked = None
    for it in items:
        vo = json.loads(get_product_detail.invoke({"product_id": it["id"]}))
        skus = vo.get("skus") or []
        in_stock = [s for s in skus if (s.get("stock") or 0) > 0]
        if in_stock:
            picked = (it, vo, in_stock[0])
            break
    check("找到有库存的商品", picked is not None)
    if not picked:
        print("\n无法继续加购验证")
        return
    prod, vo, sku = picked
    check("detail 结构含 product/skus", "product" in vo and "skus" in vo,
          f"{prod['name'][:18]}... skus={len(vo['skus'])} 首个sku库存={sku['stock']}")

    # 3. 未登录 → NeedLoginError
    print("\n[3] 未登录调 list_cart（应抛 NeedLoginError）")
    current_token.set(None)
    try:
        list_cart.invoke({})
        check("抛出 NeedLoginError", False, "（居然没抛，401 判定有问题）")
    except NeedLoginError:
        check("抛出 NeedLoginError", True)
    except Exception as e:  # noqa: BLE001
        check("抛出 NeedLoginError", False, f"（抛的是 {type(e).__name__}: {e}）")

    # 4. 登录并加购
    print("\n[4] 登录 + add_to_cart")
    try:
        mall_client.api_post(mall_client.config.PORTAL_BASE_URL, "/member/register",
                             params={"phone": PHONE, "password": PASSWORD})
    except Exception:  # noqa: BLE001 —— 已注册过会失败，忽略
        pass
    login = mall_client.api_post(mall_client.config.PORTAL_BASE_URL, "/member/login",
                                 params={"phone": PHONE, "password": PASSWORD})
    token = (login.get("data") or {}).get("token")
    check("拿到登录 token", bool(token))
    if not token:
        return

    current_token.set(token)
    # 可重复运行：先清掉该商品在购物车里的旧条目，避免数量累加
    deleted = 0
    for it in fetch_cart(token):
        if it.get("productId") == prod["id"] and it.get("skuId") == sku["id"]:
            try:
                mall_client.api_delete(mall_client.config.PORTAL_BASE_URL, "/cart/delete",
                                       params={"cartItemId": it["cartItemId"]}, token=token)
                deleted += 1
            except Exception:  # noqa: BLE001 —— 幽灵缓存条目（见缺陷 B1）删不掉，忽略
                pass
    if deleted:
        print(f"  （清理旧购物车条目 {deleted} 条）")
    res = json.loads(add_to_cart.invoke({"product_id": prod["id"], "quantity": 1}))
    cart_id = res.get("cartId")
    check("加购返回 cartId", bool(cart_id),
          f"cartId={cart_id} 名称={res.get('productName','')[:16]}... 价={res.get('price')}")

    # 5. 购物车 / 确认单复述同一个 cartId
    print("\n[5] list_cart / preview_order")
    cart = json.loads(list_cart.invoke({}))
    mine = next((c for c in cart if c.get("cartId") == cart_id), None)
    check("list_cart 含刚加的条目", mine is not None, f"购物车 {len(cart)} 条")
    check("购物车条目带图（取图口径未踩坑）", bool(mine and mine.get("pic")),
          f"pic={((mine or {}).get('pic') or '')[:52]}")
    # 确认单需要收货地址：测试账号没有就补一个
    addrs = mall_client.api_get(mall_client.config.PORTAL_BASE_URL, "/member/address/list",
                                token=token).get("data") or []
    if not addrs:
        mall_client.api_post(mall_client.config.PORTAL_BASE_URL, "/member/address/add",
                             body={"receiverName": "测试收件人", "phone": PHONE,
                                   "province": "北京市", "city": "北京市", "district": "朝阳区",
                                   "detailAddress": "测试路 1 号", "defaultStatus": 1}, token=token)
    pv = json.loads(preview_order.invoke({"cart_id": cart_id}))
    check("preview 生成确认单",
          bool(pv.get("calcAmount", {}).get("payAmount") is not None),
          f"payAmount={pv.get('calcAmount', {}).get('payAmount')} "
          f"地址数={len(pv.get('memberReceiveAddressList') or [])}")

    print(f"\n=== 结果：{ok} 通过 / {fail} 失败 ===")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
