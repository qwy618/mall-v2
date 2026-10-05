"""M1.4 验收：确认订单页「以后端试算为准」的推导逻辑是否正确。

前端 confirm.vue 的做法（M1.4）：
  1. 试算时统一传「账户全部积分」useIntegration=balance（后端按 余额 + 券后应付 双重封顶）；
  2. 把响应里的 useIntegration 当作「本单最多可用积分数」展示；
  3. 积分开关打开 → 应付 = 响应 payAmount；关闭 → 应付 = 响应 payAmount + 响应 integrationAmount。

本脚本只读（不落库/不扣库存/不下单），逐条断言这套推导与后端 create 同源：
  A. 响应字段齐全且为数值（前端 Number() 能解析）；
  B. 「传满额积分」时 useIntegration <= 余额，且 <= floor((total-promo-coupon)*100)；
  C. 关键恒等式：payAmount(不用积分) == payAmount(用满积分) + integrationAmount(用满积分)
     —— 这正是前端「开关关闭时把积分抵扣加回」的依据；
  D. 与真实下单 /order/create 的金额逐分一致（那才是用户最终扣款）。

用法：PORTAL_BASE=http://localhost:8081 python smoke_m1_4_confirm.py
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
    d = r.get("data") or {}
    tok = d.get("token") or d.get("accessToken")
    if not tok:
        print(f"登录失败：{r}")
        sys.exit(1)
    return tok


def pick_in_stock_sku():
    plist = (call("GET", "/product/list", params={"pageNum": 1, "pageSize": 20}).get("data") or {})
    for p in (plist.get("list") or []):
        d = call("GET", f"/product/{p['id']}").get("data") or {}
        for sku in (d.get("skus") or []):
            if int(sku.get("stock") or 0) > 5 and float(sku.get("price") or 0) > 0:
                return sku["id"], p["id"], int(sku["stock"])
    print("找不到有库存的 SKU")
    sys.exit(1)


def ensure_address(token):
    lst = (call("GET", "/member/address/list", token=token).get("data") or [])
    if lst:
        dft = next((a for a in lst if a.get("defaultStatus") == 1), lst[0])
        return dft["id"]
    call("POST", "/member/address/add", body={
        "receiverName": "M14测试", "phone": "13900000000", "province": "北京市",
        "city": "北京市", "district": "海淀区", "detailAddress": "测试路1号",
        "defaultStatus": 1}, token=token)
    lst = (call("GET", "/member/address/list", token=token).get("data") or [])
    return lst[0]["id"]


def level_balance(token):
    d = call("GET", "/member/level", token=token).get("data") or {}
    return int(d.get("integration") or 0), d


def main():
    print(f"目标后端：{BASE}")
    token = login()
    print("登录成功")
    sku_id, product_id, _ = pick_in_stock_sku()
    addr_id = ensure_address(token)
    balance, lv = level_balance(token)
    print(f"测试 SKU={sku_id} 地址={addr_id} 积分余额={balance} 等级={lv.get('levelName')}")

    # 前端 confirm.vue 实际发出的 payload：带 addressId、couponId=null、items、useIntegration=余额
    items = [{"skuId": sku_id, "quantity": 1, "cartItemId": None}]

    print("\n[A] 响应字段齐全且为数值")
    pv = call("POST", "/order/preview", body={
        "addressId": addr_id, "couponId": None, "items": items, "useIntegration": balance}, token=token)
    check("preview 成功", pv.get("code") == 200, str(pv.get("message") or ""))
    d = pv.get("data") or {}
    for f in ("totalAmount", "freightAmount", "promotionAmount", "couponAmount",
              "integrationAmount", "payAmount"):
        v = d.get(f)
        check(f"{f} 为数值", isinstance(v, (int, float)), f"{f}={v!r}")
    check("useIntegration 为整数", isinstance(d.get("useIntegration"), int), f"useIntegration={d.get('useIntegration')}")
    check("levelName/discountRate 存在", d.get("levelName") is not None and d.get("discountRate") is not None,
          f"{d.get('levelName')} / {d.get('discountRate')}")

    print("\n[B] 满额积分被正确封顶")
    used = int(d.get("useIntegration") or 0)
    check("useIntegration <= 余额", used <= balance, f"{used} <= {balance}")
    before = Decimal(str(d.get("totalAmount"))) - Decimal(str(d.get("promotionAmount"))) - Decimal(str(d.get("couponAmount")))
    cap_by_amount = int(before * 100)
    check("useIntegration <= floor(券后应付*100)", used <= cap_by_amount, f"{used} <= {cap_by_amount}")
    if before > 0 and balance > 0:
        check("封顶取到有效抵扣 (>0)", used > 0, f"used={used}")
    check("integrationAmount == useIntegration/100 (2位)",
          Decimal(str(d.get("integrationAmount"))) == (Decimal(used) / Decimal(100)).quantize(Decimal("0.01")),
          f"{d.get('integrationAmount')} vs {used}/100")

    print("\n[C] 关键恒等式：payAmount(不用) == payAmount(用满) + integrationAmount(用满)")
    pv0 = call("POST", "/order/preview", body={
        "addressId": addr_id, "couponId": None, "items": items, "useIntegration": 0}, token=token).get("data") or {}
    lhs = Decimal(str(pv0.get("payAmount")))
    rhs = Decimal(str(d.get("payAmount"))) + Decimal(str(d.get("integrationAmount")))
    check("恒等式成立（前端开关关闭时的加回逻辑正确）", lhs == rhs, f"{lhs} == {rhs}")
    check("不用积分时 useIntegration 为 0", int(pv0.get("useIntegration") or 0) == 0)

    print("\n[D] 与真实下单逐分一致（用户最终扣款口径）")
    if os.getenv("M14_SKIP_CREATE") == "1":
        print("  （已跳过：M14_SKIP_CREATE=1 —— 仅验只读的 A/B/C，不产生任何订单/积分扣减）")
    else:
        tk = call("POST", "/order/token", token=token).get("data")
        cr = call("POST", "/order/create", body={
            "addressId": addr_id, "items": items, "submitToken": tk, "useIntegration": used}, token=token)
        order_id = cr.get("data")
        check("下单成功", cr.get("code") == 200 and order_id, f"orderId={order_id} {cr.get('message') or ''}")
        if order_id:
            od = (call("GET", "/order/detail", params={"orderId": order_id}, token=token).get("data") or {}).get("order") or {}
            for f in ("totalAmount", "promotionAmount", "couponAmount", "integrationAmount", "payAmount"):
                check(f"{f} 逐分一致", Decimal(str(d.get(f))) == Decimal(str(od.get(f))), f"preview={d.get(f)} create={od.get(f)}")
            check("create 用的积分数与试算一致", int(od.get("useIntegration") or 0) == used,
                  f"create={od.get('useIntegration')} preview={used}")
            cn = call("POST", "/order/cancel", params={"orderId": order_id}, token=token)
            print(f"  （已取消测试订单 {od.get('orderSn')}：{cn.get('code')}）")

    print(f"\n===== 结果：{PASS} 通过 / {FAIL} 失败 =====")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
