"""M1.2 验收：/order/preview 与 /order/create 金额同源（逐分一致）+ preview 无副作用。

验的是设计中「确认卡片上的每个数字都来自下单那条链路的同一段代码」这条铁律。

可重复运行：跑完自动取消测试订单（取消会恢复库存），不留脏数据。
只读断言（preview 不落库/不扣库存/幂等）不需要产生订单。

用法：PORTAL_BASE=http://localhost:8081 python smoke_m1_preview.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

BASE = os.getenv("PORTAL_BASE", "http://localhost:8081").rstrip("/")
PHONE = os.getenv("MALL_TEST_PHONE", "13900007777")
PASSWORD = os.getenv("MALL_TEST_PWD", "Test123456")

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))


def call(method, path, params=None, body=None, token=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"code": e.code, "message": raw[:200]}


def login():
    r = call("POST", "/member/login", params={"phone": PHONE, "password": PASSWORD})
    data = r.get("data") or {}
    tok = data.get("token") or data.get("accessToken")
    if not tok:
        print(f"登录失败：{r}")
        sys.exit(1)
    return tok


def pick_in_stock_sku():
    """挑一个「有库存且价格>0」的 SKU 及其库存，返回 (skuId, productId, stock, price)。"""
    plist = (call("GET", "/product/list", params={"pageNum": 1, "pageSize": 20}).get("data") or {})
    for p in (plist.get("list") or []):
        d = call("GET", f"/product/{p['id']}").get("data") or {}
        for sku in (d.get("skus") or []):
            stock = int(sku.get("stock") or 0)
            price = float(sku.get("price") or 0)
            if stock > 5 and price > 0:
                return sku["id"], p["id"], stock, price
    print("找不到有库存的 SKU")
    sys.exit(1)


def ensure_address(token):
    """取默认地址；没有则新建一个（保证可下单）。返回 addressId。"""
    lst = (call("GET", "/member/address/list", token=token).get("data") or [])
    if lst:
        dft = next((a for a in lst if a.get("defaultStatus") == 1), lst[0])
        return dft["id"]
    call("POST", "/member/address/add", body={
        "receiverName": "M1测试", "phone": "13900000000", "province": "北京市",
        "city": "北京市", "district": "海淀区", "detailAddress": "测试路1号",
        "defaultStatus": 1}, token=token)
    lst = (call("GET", "/member/address/list", token=token).get("data") or [])
    return lst[0]["id"]


def order_total(token):
    d = call("GET", "/order/list", params={"pageNum": 1, "pageSize": 1}, token=token).get("data") or {}
    return int(d.get("total") or 0)


def sku_stock(product_id, sku_id):
    d = call("GET", f"/product/{product_id}").get("data") or {}
    for sku in (d.get("skus") or []):
        if sku.get("id") == sku_id:
            return int(sku.get("stock") or 0)
    return None


def main():
    print(f"目标后端：{BASE}")
    token = login()
    print("登录成功")
    sku_id, product_id, stock0, price = pick_in_stock_sku()
    print(f"测试 SKU：skuId={sku_id} productId={product_id} 单价={price} 初始库存={stock0}")

    addr_id = ensure_address(token)
    print(f"收货地址 id={addr_id}")
    total_before = order_total(token)

    items = [{"skuId": sku_id, "quantity": 1}]

    # ---- A. preview 基本返回 ----
    print("\n[A] preview 返回结构")
    pv = call("POST", "/order/preview", body={"items": items, "useIntegration": 0}, token=token)
    check("preview 成功", pv.get("code") == 200, str(pv.get("message") or ""))
    d = pv.get("data") or {}
    check("含 payAmount/totalAmount", d.get("payAmount") is not None and d.get("totalAmount") is not None,
          f"总={d.get('totalAmount')} 实付={d.get('payAmount')}")
    check("含行明细 + 商品图", bool(d.get("items")) and all(i.get("productPic") for i in d.get("items", [])),
          f"{len(d.get('items') or [])} 行")
    check("缺省 addressId 时取到默认地址", (d.get("address") or {}).get("id") is not None,
          f"地址 id={(d.get('address') or {}).get('id')}")
    check("等级名已返回", d.get("levelName") is not None, f"levelName={d.get('levelName')} 折扣率={d.get('discountRate')}")

    # ---- B. preview 无副作用 ----
    print("\n[B] preview 无副作用")
    check("未产生订单", order_total(token) == total_before, f"订单数 {total_before}→{order_total(token)}")
    st = sku_stock(product_id, sku_id)
    check("未扣库存", st == stock0, f"库存 {stock0}→{st}")

    # ---- C. preview 幂等（纯函数）----
    print("\n[C] preview 幂等")
    pv2 = call("POST", "/order/preview", body={"items": items, "useIntegration": 0}, token=token).get("data") or {}
    check("两次 preview 金额一致", pv2.get("payAmount") == d.get("payAmount"),
          f"{d.get('payAmount')} vs {pv2.get('payAmount')}")

    # ---- D. 与 create 逐分一致 ----
    print("\n[D] preview vs create 金额同源（逐分）")
    tk = call("POST", "/order/token", token=token).get("data")
    check("取到幂等令牌", bool(tk))
    cr = call("POST", "/order/create", body={
        "addressId": addr_id, "items": items, "submitToken": tk, "useIntegration": 0}, token=token)
    order_id = cr.get("data")
    check("下单成功", cr.get("code") == 200 and order_id, f"orderId={order_id} {cr.get('message') or ''}")
    if order_id:
        od = (call("GET", "/order/detail", params={"orderId": order_id}, token=token).get("data") or {}).get("order") or {}
        for f in ("totalAmount", "promotionAmount", "couponAmount", "integrationAmount", "payAmount"):
            a, b = d.get(f), od.get(f)
            check(f"{f} 逐分一致", Decimal(str(a)) == Decimal(str(b)), f"preview={a} create={b}")
        # 取消（恢复库存），保持可重复运行
        cn = call("POST", "/order/cancel", params={"orderId": order_id}, token=token)
        print(f"  （已取消测试订单 {od.get('orderSn')}：{cn.get('code')}）")

    print(f"\n===== 结果：{PASS} 通过 / {FAIL} 失败 =====")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
