#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portal 领券分布式锁(设计B)实测脚本
- 验证 Redisson 锁释放(不泄漏)：同一会员领第二次必须毫秒级返回"已领取过"
- 验证并发不超卖：N 个不同会员并发抢同一张券，最终 receive_count == publish_count
仅用标准库 urllib/threading/json，无需第三方依赖。
"""
import urllib.request, urllib.parse, urllib.error, json, threading, time, sys

BASE = "http://localhost:8081"
PW = "Test@123456"
N_MEMBERS = 100   # 注册的测试会员数（足够覆盖大多数券的 publishCount）

def _req(method, path, params=None, token=None, timeout=10):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=b"", method=method)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"code": -1, "message": "HTTPError %s" % e.code}

def post(path, params, token=None):
    return _req("POST", path, params, token)

def get(path, token=None):
    return _req("GET", path, None, token)

def ensure_members(n):
    tokens = []
    for i in range(1, n + 1):
        phone = "177%08d" % i          # 17700000001 ...（全新前缀，避免历史记录干扰）
        # 注册（已存在会报错，但登录仍可取 token，幂等）
        post("/member/register", {"phone": phone, "password": PW, "nickname": "lk%d" % i})
        res = post("/member/login", {"phone": phone, "password": PW})
        tok = res.get("data", {}).get("token") if isinstance(res.get("data"), dict) else None
        if not tok:
            print("  [WARN] 会员 %s 登录失败: %s" % (phone, res))
            tok = None
        tokens.append(tok)
    return tokens

def pick_coupon(strategy):
    lst = get("/coupon/list").get("data", []) or []
    avail = [c for c in lst if c.get("publishCount") and c.get("receiveCount", 0) < c["publishCount"]]
    if not avail:
        print("[FAIL] 没有剩余可领的券，无法测试"); sys.exit(1)
    if strategy == "first":
        return avail[0]
    # smallest publishCount（用于超卖测试）
    avail.sort(key=lambda c: c["publishCount"])
    return avail[0]

def main():
    print("===== 0. 准备测试会员 =====")
    tokens = ensure_members(N_MEMBERS)
    valid = [t for t in tokens if t]
    print("  成功登录会员数: %d / %d" % (len(valid), N_MEMBERS))
    if len(valid) < 5:
        print("[FAIL] 可用会员过少，终止"); sys.exit(1)

    # ---- 功能验证：锁释放(不泄漏) ----
    print("\n===== 1. 功能验证：锁释放(不泄漏) =====")
    ca = pick_coupon("first")
    cid = ca["id"]; pub = ca["publishCount"]
    print("  使用券 id=%s publishCount=%s" % (cid, pub))
    t0 = time.time()
    r1 = post("/coupon/receive", {"couponId": cid}, valid[0])
    c1 = time.time() - t0
    print("  第1次领取 -> %s (耗时 %.0f ms)" % (r1.get("message"), c1 * 1000))
    t0 = time.time()
    r2 = post("/coupon/receive", {"couponId": cid}, valid[0])
    c2 = time.time() - t0
    print("  第2次领取(同会员) -> %s (耗时 %.0f ms)" % (r2.get("message"), c2 * 1000))
    if c2 < 1.5 and "已领取" in (r2.get("message") or ""):
        print("  [PASS] 锁已正确释放：第二次未卡 3 秒，且正常判定重复领取")
    else:
        print("  [FAIL] 疑似锁泄漏：第二次领取耗时 %.0f ms，或返回异常: %s" % (c2 * 1000, r2))

    # ---- 并发超卖验证 ----
    print("\n===== 2. 并发超卖验证 =====")
    lst = get("/coupon/list").get("data", []) or []
    avail = [c for c in lst if c.get("publishCount") and c.get("receiveCount", 0) < c["publishCount"]]
    if not avail:
        print("[FAIL] 没有剩余可领的券，无法测试"); sys.exit(1)
    avail.sort(key=lambda c: c["publishCount"])
    cb = avail[0]
    cid2 = cb["id"]; pub2 = cb["publishCount"]; r0 = cb.get("receiveCount", 0)
    remaining = pub2 - r0
    print("  目标券 id=%s publishCount=%s 当前receiveCount=%s 剩余=%s"
          % (cid2, pub2, r0, remaining))
    # 用功能测试之外的新鲜会员批次（valid[0] 已领过券A），按 剩余+溢出 发请求
    overflow = 20
    fire = min(remaining + overflow, len(valid) - 1)
    workers = valid[1:1 + fire]
    print("  并发发起 %d 个不同会员的领取请求（比剩余量多 %d）"
          % (len(workers), len(workers) - remaining))

    results = [None] * len(workers)
    lock = threading.Lock()
    def worker(idx, tok):
        r = post("/coupon/receive", {"couponId": cid2}, tok)
        with lock:
            results[idx] = r
    threads = []
    t0 = time.time()
    for i, tok in enumerate(workers):
        th = threading.Thread(target=worker, args=(i, tok))
        threads.append(th)
        th.start()
    for th in threads:
        th.join()
    cost = time.time() - t0

    succ = sum(1 for r in results if r and r.get("code") == 200)
    soldout = sum(1 for r in results if r and "抢光" in (r.get("message") or ""))
    errs = sum(1 for r in results if r and r.get("code") not in (200,)
               and "抢光" not in (r.get("message") or ""))
    print("  并发总耗时 %.0f ms" % (cost * 1000))
    print("  结果统计: 成功(领取到)=%d  已抢光=%d  其他错误=%d" % (succ, soldout, errs))

    # 读取最终 receive_count（再次拉列表）
    final = None
    for c in (get("/coupon/list").get("data", []) or []):
        if c.get("id") == cid2:
            final = c.get("receiveCount")
            break
    expected_succ = min(remaining, len(workers))
    cap_hit = len(workers) >= remaining
    print("  最终 receive_count = %s (期望上限 publishCount=%s)" % (final, pub2))
    ok = (final is not None) and (final <= pub2) and (succ == expected_succ)
    if cap_hit:
        ok = ok and (final == pub2)
    if ok:
        print("  [PASS] 未超卖：receive_count=%s <= publishCount=%s，成功领取=%s（剩余=%s，溢出请求均被'已抢光'拦截）"
              % (final, pub2, succ, remaining))
    else:
        print("  [FAIL] 超卖或统计异常：final=%s succ=%s pub2=%s remaining=%s" % (final, succ, pub2, remaining))

    print("\n===== 测试结束 =====")

if __name__ == "__main__":
    main()
