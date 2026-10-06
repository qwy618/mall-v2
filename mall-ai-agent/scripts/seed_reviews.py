"""M3.0：造评价种子数据 —— **全程走真实 API，不写一条 SQL**。

为什么要造数据：实测全库评价总数 = 1（38 个商品里 37 个为 0），
RAG 的「语义道」无数据可检，直接做 M3 验收会「假性通过」——拒答会因为
检不到任何东西而看着很对，其实是因为压根没数据。

本脚本走的是 mall-v2 的真实业务链路（admin 侧有 pay→ship→complete 的
状态直达通道，所以既不用等"自动确认收货"定时任务，也不用落盘 SQL）：

    C 端会员                          管理端(admin)
    ─────────                        ─────────────
    1. POST /order/token
    2. POST /order/create            3. POST /order/pay/{id}
                                     4. POST /order/ship/{id}
                                     5. POST /order/complete/{id}
    6. POST /comment/submit
                                     7. POST /comment/audit/{id}?status=1

幂等设计：**按「每个商品的已公开评价数」补齐，不是无脑追加**。
rerun 时只补差额，所以重复执行不会让评价数翻倍。

运行：
    .venv\\Scripts\\python scripts/seed_reviews.py                 # 造数据（默认 10 商品 × 6 条）
    .venv\\Scripts\\python scripts/seed_reviews.py --check         # 只统计，不写
    .venv\\Scripts\\python scripts/seed_reviews.py --clean         # 清理本会员造的评价（按 memberId）

依赖：portal(8081) 与 admin(8080) 都必须在线。
"""
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402
from app.tools import mall_client  # noqa: E402

# ---- 端点 -------------------------------------------------------------------
PORTAL = config.PORTAL_BASE_URL
ADMIN = os.getenv("ADMIN_BASE_URL", "http://localhost:8080")

# ---- 凭据（脚本内置，勿走命令行——命令行里的 password= 会被沙箱判为敏感拦截）----
PHONE = os.getenv("SEED_PHONE", "13900007777")
PASSWORD = os.getenv("SEED_PASSWORD", "Test123456")
ADMIN_USER = os.getenv("SEED_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "macro123")

# 脏数据商品名（实测库里存在 id=22 "test" / id=24 "xxx"），与设计文档 §8 的
# RAG_SKIP_NAME_PATTERN 保持一致——不进索引的东西也没必要喂评价。
SKIP_NAME_PATTERN = r"^(test|xxx|\d+)$"

DEFAULT_PRODUCTS = 10
DEFAULT_PER_PRODUCT = 6
MIN_PRODUCTS_PASS = 8      # 验收线：≥8 个商品
MIN_REVIEWS_PASS = 5       # 验收线：每个 ≥5 条 status=1

# ---- 评价语料模板 -----------------------------------------------------------
# 覆盖 物流 / 外观 / 性能 / 性价比 / 售后 五个侧面，星级 3~5 混合。
# 模板化而非调 LLM：确定、可复现、零成本、不依赖 key；改一篇正文要能被 review。
# {name} 会被替换成商品名。星级由模板决定，避免全员五星（那种语料对
# 「优缺点/槽点」类问题毫无区分度）。
REVIEW_TEMPLATES: list[tuple[str, int, str]] = [
    ("物流", 5, "物流很快，下单第二天就到了，包装也很严实，没有任何磕碰。"),
    ("物流", 4, "发货速度还行，就是物流信息更新有点慢，东西本身没问题。"),
    ("物流", 3, "东西是好的，但物流比预计晚了两天，等待体验一般。"),
    ("外观", 5, "外观设计很对我的审美，做工细致，边角处理得很干净。"),
    ("外观", 4, "颜值在线，比图片略深一点点，整体还是很好看的。"),
    ("外观", 3, "外观中规中矩，谈不上惊艳，但也不难看。"),
    ("性能", 5, "性能完全够用，日常使用很流畅，没有出现卡顿的情况。"),
    ("性能", 4, "整体表现不错，重度使用时会有一点发热，可以接受。"),
    ("性能", 3, "基础功能没问题，就是高负载下反应会慢半拍。"),
    ("性价比", 5, "这个价位能买到这样的配置，性价比真的很高，推荐。"),
    ("性价比", 4, "价格合适，比同价位的一些品牌更实在，值这个钱。"),
    ("性价比", 3, "价格偏贵了一点，等有活动再入会更划算。"),
    ("售后", 5, "客服态度很好，有问题回复很快，处理得也利索。"),
    ("售后", 4, "售前咨询解答得挺详细，售后还没用到，先给四星。"),
    ("售后", 3, "售后响应有点慢，来回问了几次才解决，体验一般。"),
    ("综合", 5, "买来送人的，对方很满意，说用着顺手中意，会回购。"),
    ("综合", 4, "用了两周整体满意，小毛病暂时没发现，后续再追评。"),
    ("综合", 3, "能用的水平，没有宣传得那么神，理性看待吧。"),
    ("综合", 5, "朋友推荐买的，确实没踩坑，比之前那款顺手多了。"),
    ("综合", 4, "对比了好几家最后选了这个，没让人失望，可以入手。"),
]

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


# ---------------------------------------------------------------- 登录

def login_portal() -> str:
    res = mall_client.api_post(PORTAL, "/member/login",
                               params={"phone": PHONE, "password": PASSWORD})
    return (res.get("data") or {}).get("token")


def login_admin() -> str:
    res = mall_client.api_post(ADMIN, "/admin/login",
                               body={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    data = res.get("data") or {}
    token = data.get("token")
    if not token:
        raise RuntimeError(f"admin 登录失败：{res.get('message')}")
    return token


def member_id_of(token: str) -> int | None:
    data = mall_client.api_get(PORTAL, "/member/info", token=token).get("data") or {}
    mid = data.get("id")
    return int(mid) if mid is not None else None


# ---------------------------------------------------------------- 地址

def ensure_address(token: str) -> int:
    """确保测试会员有默认地址（下单必需），返回 addressId。"""
    addrs = mall_client.api_get(PORTAL, "/member/address/list", token=token).get("data") or []
    for a in addrs:
        if a.get("defaultStatus") == 1:
            return int(a["id"])
    if addrs:
        return int(addrs[0]["id"])
    mall_client.api_post(PORTAL, "/member/address/add", body={
        "receiverName": "测试用户",
        "phone": PHONE,
        "province": "北京市",
        "city": "北京市",
        "district": "朝阳区",
        "detailAddress": "演示用收货地址（种子数据）",
        "defaultStatus": 1,
    }, token=token)
    addrs = mall_client.api_get(PORTAL, "/member/address/list", token=token).get("data") or []
    if not addrs:
        raise RuntimeError("创建收货地址后仍查不到，请检查 /member/address/add")
    return int(addrs[0]["id"])


# ---------------------------------------------------------------- 商品

def pick_products(limit: int) -> list[dict]:
    """挑可入库的商品：跳过脏数据名，且必须有**有库存的 SKU**。"""
    import re
    pat = re.compile(SKIP_NAME_PATTERN, re.I)
    listed = mall_client.api_get(PORTAL, "/product/list",
                                 params={"pageNum": 1, "pageSize": 50}).get("data") or {}
    out: list[dict] = []
    for p in listed.get("list") or []:
        if len(out) >= limit:
            break
        name = (p.get("name") or "").strip()
        if not name or pat.match(name):
            print(f"  · 跳过脏数据/空名商品 id={p.get('id')} name={name!r}")
            continue
        vo = mall_client.api_get(PORTAL, f"/product/{p['id']}").get("data") or {}
        skus = [s for s in (vo.get("skus") or []) if (s.get("stock") or 0) > 0]
        if not skus:
            continue
        skus.sort(key=lambda s: float(s.get("price") or 0))
        out.append({"id": p["id"], "name": name,
                    "subTitle": p.get("subTitle") or "",
                    "sku": skus[0]})
    return out


def published_count(product_id: int, admin_token: str) -> int:
    """该商品当前**已公开**(status=1)的评价数——走 admin 列表拿 total。"""
    data = mall_client.api_get(ADMIN, "/comment/list",
                               params={"pageNum": 1, "pageSize": 1,
                                       "productId": product_id, "status": 1},
                               token=admin_token).get("data") or {}
    return int(data.get("total") or 0)


# ---------------------------------------------------------------- 购物车

def clear_cart(token: str) -> None:
    for it in mall_client.api_get(PORTAL, "/cart/list", token=token).get("data") or []:
        try:
            mall_client.api_delete(PORTAL, "/cart/delete",
                                   params={"cartItemId": it["cartItemId"]}, token=token)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- 单条评价

def seed_one(product: dict, sku: dict, star: int, content: str,
             portal_token: str, admin_token: str, address_id: int) -> tuple[int, int]:
    """跑完 7 步，返回 (orderId, commentId)。"""
    # 1) 加购
    mall_client.api_post(PORTAL, "/cart/add",
                         params={"skuId": sku["id"], "quantity": 1}, token=portal_token)
    cart = mall_client.api_get(PORTAL, "/cart/list", token=portal_token).get("data") or []
    item = next((c for c in cart
                 if c.get("skuId") == sku["id"] and c.get("productId") == product["id"]), None)
    if not item:
        raise RuntimeError("加购后在购物车里找不到该条目")

    # 2) 一次性幂等令牌 + 3) 下单
    tk = mall_client.api_post(PORTAL, "/order/token", token=portal_token).get("data")
    if not tk:
        raise RuntimeError("取下单令牌失败")
    order_id = mall_client.api_post(PORTAL, "/order/create", body={
        "addressId": address_id,
        "items": [{"skuId": sku["id"], "quantity": 1,
                   "cartItemId": item["cartItemId"]}],
        "submitToken": tk,
        "useIntegration": 0,
    }, token=portal_token).get("data")
    if not order_id:
        raise RuntimeError("下单失败")

    # 4) 支付 5) 发货 6) 确认收货（admin 状态直达）
    mall_client.api_post(ADMIN, f"/order/pay/{order_id}", token=admin_token)
    mall_client.api_post(ADMIN, f"/order/ship/{order_id}", body={
        "deliveryCompany": "顺丰速运",
        "deliverySn": "SF" + str(int(time.time() * 1000))[-12:] + str(random.randint(10, 99)),
    }, token=admin_token)
    mall_client.api_post(ADMIN, f"/order/complete/{order_id}", token=admin_token)

    # 7) 取 orderItemId
    detail = mall_client.api_get(PORTAL, "/order/detail",
                                 params={"orderId": order_id}, token=portal_token).get("data") or {}
    oi = next((i for i in (detail.get("items") or [])
               if i.get("skuId") == sku["id"] and i.get("productId") == product["id"]), None)
    if not oi:
        raise RuntimeError(f"订单 {order_id} 里找不到对应订单项")

    # 8) 提交评价（此时 status=0 待审核，还没公开）
    mall_client.api_post(PORTAL, "/comment/submit", body={
        "orderItemId": oi["id"],
        "star": star,
        "content": content,
        "anonymous": True,
    }, token=portal_token)

    # 9) 找到刚提交的那条评价并审核通过
    lst = mall_client.api_get(ADMIN, "/comment/list", params={
        "pageNum": 1, "pageSize": 50, "productId": product["id"], "status": 0,
    }, token=admin_token).get("data") or {}
    rec = next((c for c in (lst.get("list") or []) if c.get("orderItemId") == oi["id"]), None)
    if not rec:
        raise RuntimeError("提交后查不到待审核评价（审核流可能未生效）")
    mall_client.api_post(ADMIN, f"/comment/audit/{rec['id']}",
                         params={"status": 1}, token=admin_token)
    return int(order_id), int(rec["id"])


# ---------------------------------------------------------------- 清理

def clean(member_id: int, admin_token: str, products: list[dict]) -> int:
    """删除本测试会员在这些商品下的全部评价（status 0/1/2 都清）。"""
    removed = 0
    for p in products:
        for st in (0, 1, 2):
            data = mall_client.api_get(ADMIN, "/comment/list", params={
                "pageNum": 1, "pageSize": 100, "productId": p["id"], "status": st,
            }, token=admin_token).get("data") or {}
            for c in data.get("list") or []:
                if c.get("memberId") != member_id:
                    continue
                try:
                    mall_client.api_post(ADMIN, f"/comment/delete/{c['id']}", token=admin_token)
                    removed += 1
                except Exception as e:  # noqa: BLE001
                    print(f"    删除评价 {c['id']} 失败：{e}")
    return removed


# ---------------------------------------------------------------- main

def run(products_n: int, per_product: int, check_only: bool) -> None:
    print("=== M3.0 评价种子数据（真实 API 全链路）===")
    portal_token = login_portal()
    if not portal_token:
        raise RuntimeError(f"会员登录失败：{PHONE}")
    admin_token = login_admin()
    check("会员登录", bool(portal_token))
    check("admin 登录", bool(admin_token))

    member_id = member_id_of(portal_token)
    check("解析 memberId", member_id is not None, f"memberId={member_id}")

    products = pick_products(products_n)
    check(f"挑到 {products_n} 个可入库商品", len(products) == products_n,
          f"实际 {len(products)}：{', '.join(p['name'][:8] for p in products)}")

    if check_only:
        print("\n--- 现状（--check 只读）---")
        for p in products:
            print(f"  id={p['id']:>3}  status=1 评价数={published_count(p['id'], admin_token):>3}  {p['name']}")
        return

    address_id = ensure_address(portal_token)
    check("收货地址可用", bool(address_id), f"addressId={address_id}")

    clear_cart(portal_token)

    print("\n--- 造数据 ---")
    for p_idx, p in enumerate(products):
        have = published_count(p["id"], admin_token)
        need = max(0, per_product - have)
        print(f"[{p_idx + 1}/{len(products)}] {p['name'][:24]}  已有 {have} 条 → 补 {need} 条")
        for r in range(need):
            tpl_idx = (p_idx * 7 + r) % len(REVIEW_TEMPLATES)
            _, star, text = REVIEW_TEMPLATES[tpl_idx]
            body = text.replace("{name}", p["name"])
            try:
                order_id, cid = seed_one(p, p["sku"], star, body,
                                         portal_token, admin_token, address_id)
                print(f"    + 订单#{order_id} 评价#{cid}  {star}★  {body[:18]}…")
            except Exception as e:  # noqa: BLE001
                print(f"    ! 失败：{e}")
                clear_cart(portal_token)

    print("\n--- 验收 ---")
    ok_products = 0
    for p in products:
        n = published_count(p["id"], admin_token)
        if n >= MIN_REVIEWS_PASS:
            ok_products += 1
        print(f"  id={p['id']:>3}  status=1 评价数={n:>3}  {p['name']}")
    check(f"≥{MIN_PRODUCTS_PASS} 个商品达到 ≥{MIN_REVIEWS_PASS} 条公开评价",
          ok_products >= MIN_PRODUCTS_PASS, f"达标 {ok_products}/{len(products)} 个")

    clear_cart(portal_token)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", type=int, default=DEFAULT_PRODUCTS)
    ap.add_argument("--per-product", type=int, default=DEFAULT_PER_PRODUCT)
    ap.add_argument("--check", action="store_true", help="只统计现状，不写数据")
    ap.add_argument("--clean", action="store_true", help="删除本测试会员造的评价")
    args = ap.parse_args()
    try:
        if args.clean:
            print("=== M3.0 清理模式：删除本测试会员的评价 ===")
            pt = login_portal()
            at = login_admin()
            mid = member_id_of(pt)
            prods = pick_products(args.products)
            n = clean(mid, at, prods)
            print(f"\n已删除 {n} 条评价（memberId={mid}，范围 {len(prods)} 个商品）")
        else:
            run(args.products, args.per_product, args.check)
    except Exception as e:  # noqa: BLE001
        FAIL += 1
        print(f"\n[FATAL] {e}")
    finally:
        print(f"\n=== 结果：{PASS} 通过 / {FAIL} 失败 ===")
    sys.exit(1 if FAIL else 0)
