#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品域债务1（属性表）实测脚本 —— 仅用标准库，无需第三方依赖。

前置：portal 跑在 8081、admin 跑在 8080。

覆盖面：
  A. portal 详情：有参数的商品返回 attributes/specOptions；无参数商品返回空数组而非报错
  B. admin 属性接口：按分类/类型分页查、按商品查定义、参数值读写、重名与受保护删除被拦
  C. SKU 保存 → sku_attribute_value 同步（债务1 的核心：sp_data 是真源，索引是派生）
     C1 新建 SKU → 规格值被拆成索引行（用 portal 的 specOptions 反证写入成功）
     C2 新值自动补进候选值清单（管理端下拉即刻可选，运营不必先去配属性）
     C3 改规格 → 旧行被清、新行写入（幂等 delete+insert）
     C4 sp_data 非法 → SKU 仍能保存（脏数据不该卡住运营），且不产生任何索引行
     C5 全新属性名 → 自动创建属性定义（存量商品无需人工先配属性）
     C6 删除 SKU → 索引行随之清掉，不留孤儿
  D. 清理还原（脚本自己造的数据自己收干净）

用法： python test_product_attribute.py
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

ADMIN = "http://localhost:8080"
PORTAL = "http://localhost:8081"
ADMIN_USER = "admin"
ADMIN_PASS = "macro123"

# 测试商品：37 = iPhone 14（分类 19 手机通讯，规格 = 颜色 + 容量）
TEST_PID = 37
# 这些值明显是测试数据，且不会与库内既有取值重合
V1 = "脚本测试值A"
V2 = "脚本测试值B"
NEW_ATTR_NAME = "脚本测试规格"

_ok = 0
_fail = 0
_notes = []


def check(name, cond, detail=""):
    global _ok, _fail
    if cond:
        _ok += 1
        print("  [PASS] %s" % name)
    else:
        _fail += 1
        print("  [FAIL] %s  %s" % (name, detail))


def note(msg):
    _notes.append(msg)


def req(base, method, path, params=None, body=None, token=None, timeout=20):
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", token)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"code": -1, "message": "HTTP %s" % e.code}
    except Exception as e:
        return {"code": -1, "message": str(e)}


def options_of(attr):
    """属性定义里的候选值清单 → list"""
    return [s for s in (attr.get("inputList") or "").split(",") if s.strip()]


def spec_options_map():
    """portal 详情 → {属性名: [可选值]}，用来反证 sku_attribute_value 的内容"""
    d = req(PORTAL, "GET", "/product/%d" % TEST_PID)
    vo = d.get("data") or {}
    return {o.get("name"): list(o.get("values") or []) for o in (vo.get("specOptions") or [])}


def sku_count():
    d = req(PORTAL, "GET", "/product/%d" % TEST_PID)
    return len((d.get("data") or {}).get("skus") or [])


# ============================================================
# A. portal 详情
# ============================================================
def section_a():
    print("\n=== A. portal 详情返回参数与规格选项 ===")
    d = req(PORTAL, "GET", "/product/%d" % TEST_PID)
    vo = d.get("data") or {}
    attrs = vo.get("attributes")
    opts = vo.get("specOptions")
    check("A1 有参数的商品返回非空 attributes",
          isinstance(attrs, list) and len(attrs) > 0, str(attrs)[:140])
    check("A2 每条参数都含 name/value",
          bool(attrs) and all(a.get("name") and a.get("value") for a in attrs))
    check("A3 specOptions 按属性名分组且每组有值",
          isinstance(opts, list) and len(opts) >= 1
          and all(o.get("name") and o.get("values") for o in opts), str(opts)[:140])
    # 参数与规格不能串：参数不应出现在 specOptions 里
    param_names = {a.get("name") for a in (attrs or [])}
    spec_names = {o.get("name") for o in (opts or [])}
    check("A4 参数与规格互不混淆（两张表各管一件事）",
          not (param_names & spec_names), "交集=%s" % (param_names & spec_names))

    # 无参数商品必须优雅降级，而不是 500
    d2 = req(PORTAL, "GET", "/product/1")
    vo2 = d2.get("data") or {}
    check("A5 无参数商品返回空数组而非报错",
          vo2.get("attributes") == [] and vo2.get("specOptions") == [], str(d2)[:140])


# ============================================================
# B. admin 属性接口
# ============================================================
def section_b(token):
    print("\n=== B. admin 属性接口 ===")
    r = req(ADMIN, "GET", "/attribute/list",
            params={"categoryId": 19, "type": 0, "pageNum": 1, "pageSize": 100}, token=token)
    specs = (r.get("data") or {}).get("list") or []
    check("B1 按分类+类型查规格属性", r.get("code") == 200 and len(specs) > 0, str(r)[:140])

    r = req(ADMIN, "GET", "/attribute/list",
            params={"categoryId": 19, "type": 1, "pageNum": 1, "pageSize": 100}, token=token)
    params_ = (r.get("data") or {}).get("list") or []
    check("B2 按分类+类型查参数属性", r.get("code") == 200 and len(params_) > 0, str(r)[:140])
    check("B3 参数属性一律手工录入(inputType=0)",
          bool(params_) and all(a.get("inputType") == 0 for a in params_))

    r = req(ADMIN, "GET", "/attribute/listByProduct",
            params={"productId": TEST_PID, "type": 0}, token=token)
    by_prod = r.get("data") or []
    check("B4 按商品查规格定义（内部解析了商品分类）",
          r.get("code") == 200 and {a.get("name") for a in by_prod} >= {"颜色", "容量"},
          str(by_prod)[:140])

    # 参数值读取 + 覆盖式写回（用一个不影响展示的临时参数试，随后还原）
    r = req(ADMIN, "GET", "/attribute/productParams", params={"productId": TEST_PID}, token=token)
    origin = r.get("data") or []
    check("B5 读取商品参数值", r.get("code") == 200 and len(origin) > 0, str(r)[:140])

    if origin:
        target = origin[0]
        marker = target["value"] + "-临时"
        tmp = [{"attributeId": a["attributeId"], "value": a["value"]} for a in origin]
        tmp[0]["value"] = marker
        r = req(ADMIN, "POST", "/attribute/productParams/%d" % TEST_PID, body=tmp, token=token)
        check("B6 覆盖式保存商品参数", r.get("code") == 200, str(r)[:140])
        r = req(ADMIN, "GET", "/attribute/productParams", params={"productId": TEST_PID}, token=token)
        now = r.get("data") or []
        check("B7 参数确实被改写且行数不变",
              len(now) == len(origin) and any(a["value"] == marker for a in now), str(now)[:140])
        # 还原
        back = [{"attributeId": a["attributeId"], "value": a["value"]} for a in origin]
        req(ADMIN, "POST", "/attribute/productParams/%d" % TEST_PID, body=back, token=token)
        r = req(ADMIN, "GET", "/attribute/productParams", params={"productId": TEST_PID}, token=token)
        check("B8 参数已还原", (r.get("data") or []) == origin)

    # 重名拦截（属性按分类隔离，同分类下重名应被业务异常拦住而不是抛 500）
    if by_prod:
        dup = {"categoryId": 19, "name": by_prod[0]["name"], "type": 0}
        r = req(ADMIN, "POST", "/attribute/create", body=dup, token=token)
        check("B9 同分类重名被可读地拦截",
              r.get("code") != 200 and "已存在" in (r.get("message") or ""), str(r)[:140])

    # 已被取值使用的属性不允许删除（防静默丢数据）
    if specs:
        used = next((a for a in specs if a.get("name") == "颜色"), specs[0])
        r = req(ADMIN, "POST", "/attribute/delete/%d" % used["id"], token=token)
        check("B10 已被取值使用的属性拒绝删除",
              r.get("code") != 200 and "取值" in (r.get("message") or ""), str(r)[:140])

    return by_prod, origin


# ============================================================
# C. SKU 保存 → 派生索引同步
# ============================================================
def section_c(token, spec_defs, origin_params):
    print("\n=== C. SKU 保存 → 规格派生索引同步 ===")
    names = [a["name"] for a in spec_defs]
    if len(names) < 2:
        check("C0 该商品有两个规格属性可供测试", False, str(names))
        return []
    k1, k2 = names[0], names[1]
    v1 = options_of(spec_defs[0])[0]     # 一个已有取值
    created = []
    base_skus = sku_count()
    base_opts = spec_options_map()
    origin_k2_input = spec_defs[1].get("inputList") or ""

    def create_sku(sp):
        r = req(ADMIN, "POST", "/sku/create",
                body={"productId": TEST_PID, "spData": sp, "price": 1.00, "stock": 1}, token=token)
        if isinstance(r.get("data"), int):
            created.append(r["data"])
        return r

    # C1 / C2：新值 V1 只可能来自这个 SKU —— 它出现在 specOptions 就证明索引行写进去了
    sp = json.dumps([{"key": k1, "value": v1}, {"key": k2, "value": V1}], ensure_ascii=False)
    r = create_sku(sp)
    check("C1 新建 SKU 成功", isinstance(r.get("data"), int), str(r)[:140])
    check("C1b SKU 数 +1", sku_count() == base_skus + 1)

    opts = spec_options_map()
    check("C2 新 SKU 的规格值已写入派生索引（specOptions 出现 %s）" % V1,
          V1 in opts.get(k2, []), str(opts.get(k2)))

    r = req(ADMIN, "GET", "/attribute/listByProduct",
            params={"productId": TEST_PID, "type": 0}, token=token)
    defs_now = {a["name"]: a for a in (r.get("data") or [])}
    check("C2b 新取值自动补进候选值清单（运营下拉即刻可选）",
          V1 in options_of(defs_now.get(k2, {})), str(defs_now.get(k2, {}).get("inputList"))[:160])

    # C3：改成 V2 → 旧行被清、新行写入
    if created:
        sid = created[0]
        sp2 = json.dumps([{"key": k1, "value": v1}, {"key": k2, "value": V2}], ensure_ascii=False)
        r = req(ADMIN, "POST", "/sku/update/%d" % sid,
                body={"productId": TEST_PID, "spData": sp2, "price": 1.00, "stock": 1}, token=token)
        check("C3 修改 SKU 规格成功", r.get("code") == 200, str(r)[:140])
        vals = spec_options_map().get(k2, [])
        check("C3b 旧值已从索引移除（delete+insert 幂等）", V1 not in vals, str(vals))
        check("C3c 新值已写入索引", V2 in vals, str(vals))

    # C4：非法 sp_data —— 不能卡住运营，且不该产生任何索引行
    before_names = set(spec_options_map().keys())
    r = create_sku("not-a-json-at-all")
    check("C4 非法 sp_data 仍能保存 SKU（脏数据不阻塞运营）",
          isinstance(r.get("data"), int), str(r)[:140])
    check("C4b 非法 sp_data 不产生任何索引行",
          set(spec_options_map().keys()) == before_names)

    # C5：全新属性名 → 自动建属性定义（存量商品无需先配属性）
    sp3 = json.dumps([{"key": NEW_ATTR_NAME, "value": V1}], ensure_ascii=False)
    r = create_sku(sp3)
    check("C5 用未定义的属性名建 SKU 成功", isinstance(r.get("data"), int), str(r)[:140])
    opts3 = spec_options_map()
    check("C5b 属性定义被自动创建且值已入索引",
          NEW_ATTR_NAME in opts3 and V1 in opts3[NEW_ATTR_NAME], str(opts3.get(NEW_ATTR_NAME)))

    # C6：删除全部测试 SKU → 索引随之清掉
    for sid in created:
        req(ADMIN, "POST", "/sku/delete/%d" % sid, token=token)
    check("C6 测试 SKU 已全部删除", sku_count() == base_skus, "now=%d base=%d" % (sku_count(), base_skus))
    opts4 = spec_options_map()
    check("C6b 删除 SKU 后其索引行一并清掉（无孤儿行）",
          V1 not in opts4.get(k2, []) and V2 not in opts4.get(k2, [])
          and NEW_ATTR_NAME not in opts4, str(opts4))

    # 还原：删掉自动创建的属性定义 + 还原候选值清单里被追加的 V1/V2
    r = req(ADMIN, "GET", "/attribute/listByProduct",
            params={"productId": TEST_PID, "type": 0}, token=token)
    for a in (r.get("data") or []):
        if a["name"] == NEW_ATTR_NAME:
            rr = req(ADMIN, "POST", "/attribute/delete/%d" % a["id"], token=token)
            check("C7 自动创建的属性定义可被删除（已无取值）", rr.get("code") == 200, str(rr)[:140])
        elif a["name"] == k2:
            rr = req(ADMIN, "POST", "/attribute/update/%d" % a["id"],
                     body={"categoryId": a["categoryId"], "name": a["name"], "type": a["type"],
                           "inputType": a["inputType"], "inputList": origin_k2_input,
                           "sort": a["sort"]}, token=token)
            check("C8 候选值清单已还原", rr.get("code") == 200, str(rr)[:140])

    check("C9 最终 specOptions 与测试前一致", spec_options_map() == base_opts,
          "now=%s base=%s" % (spec_options_map(), base_opts))
    return created


def main():
    print("商品域债务1（属性表）验收 —— portal=%s admin=%s" % (PORTAL, ADMIN))
    section_a()

    r = req(ADMIN, "POST", "/admin/login", body={"username": ADMIN_USER, "password": ADMIN_PASS})
    data = r.get("data") or {}
    token = (data.get("tokenHead") or "") + (data.get("token") or "")
    if not token.strip():
        print("\n[FATAL] admin 登录失败，后续 admin 用例全部跳过：%s" % (r.get("message") or r))
        return 1
    print("  admin 登录成功")

    spec_defs, origin_params = section_b(token)
    section_c(token, spec_defs, origin_params)

    print("\n" + "=" * 56)
    print("断言合计：%d 通过 / %d 失败" % (_ok, _fail))
    if _notes:
        print("注意事项：")
        for n in _notes:
            print("  · %s" % n)
    print("=" * 56)
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
