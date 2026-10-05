"""M1.1 验收：状态外置（会话/草稿迁 Redis）。

覆盖两条硬指标：
  ① 重启服务后会话可续聊   —— 由「另起进程读会话」+「杀掉服务再读」双重证明
  ② 多实例不串会话         —— 起两个独立服务进程（共享 Redis），交叉读写互不干扰

外加状态层回归：会话归属校验、草稿原子消费、结果回放、按轮裁剪。
不需要 LLM（不调 /api/chat），因此不依赖 DEEPSEEK_API_KEY。

运行：.venv\\Scripts\\python scripts/smoke_m1_state.py
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402

from app import sessions, store  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")
    return ok


def free_ports_ok(*ports: int) -> bool:
    import socket
    for p in ports:
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
        except OSError:
            return False
        finally:
            s.close()
    return True


# ============================================================ Part A 状态层


def part_a_state_layer():
    print("\n===== Part A：状态层（直连 store，不经 HTTP）=====")
    sid_a, sid_b = "m1test-a", "m1test-b"
    store.clear_session(sid_a)
    store.clear_session(sid_b)

    # --- A1 会话读写 + 归属校验 ---
    msgs = [HumanMessage(content="我叫小明"), AIMessage(content="你好，小明")]
    sessions.reset_history(sid_a, msgs, member_id=1001)
    got = sessions.get_history(sid_a, member_id=1001)
    check("A1 会话可读回（条数与内容一致）",
          len(got) == 2 and got[0].content == "我叫小明",
          f"读回 {len(got)} 条")

    check("A2 归属校验：他人读同一 sid 得到空会话",
          sessions.get_history(sid_a, member_id=9999) == [])

    # --- A3 另起进程读会话（证明状态真的在进程外）---
    code = (
        "import sys; sys.path.insert(0, r'%s');"
        "from app import sessions;"
        "h = sessions.get_history('%s', 1001);"
        "print(len(h), h[0].content if h else '')" % (str(ROOT), sid_a)
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    check("A3 另起进程能读到同一会话（状态已出进程）",
          out.stdout.strip().startswith("2 我叫小明"),
          out.stdout.strip() or out.stderr.strip()[:120])

    # --- A4 双会话互不干扰 ---
    sessions.reset_history(sid_b, [HumanMessage(content="我是小红")], member_id=2002)
    a = sessions.get_history(sid_a, 1001)
    b = sessions.get_history(sid_b, 2002)
    check("A4 两个会话互不串",
          a[0].content == "我叫小明" and b[0].content == "我是小红")

    # --- A5 清空 ---
    sessions.clear(sid_a)
    check("A5 clear 后会话为空", sessions.get_history(sid_a, 1001) == [])

    # --- A6 分级装配：压缩视图不破坏 tool 配对（不会出现"孤儿 ToolMessage"）---
    big = []
    for i in range(6):
        big += [
            HumanMessage(content=f"第{i}问"),
            AIMessage(content="", tool_calls=[{"name": "search_products", "args": {"k": i}, "id": f"c{i}"}]),
            ToolMessage(content=json.dumps(
                [{"id": 100 + i, "name": f"商品{i}", "price": 199,
                  "pic": "http://oss/" + "x" * 400, "sale": 9}], ensure_ascii=False),
                tool_call_id=f"c{i}", name="search_products"),
            AIMessage(content=f"第{i}答"),
        ]
    keep_budget, keep_hot = sessions.TOKEN_BUDGET, sessions.HOT_ROUNDS
    sessions.TOKEN_BUDGET = 900          # 逼出降级
    sessions.HOT_ROUNDS = 2
    view, level = sessions._assemble(sid_a, big, [HumanMessage(content="再看看")])
    sessions.TOKEN_BUDGET, sessions.HOT_ROUNDS = keep_budget, keep_hot

    def _paired(msgs) -> bool:
        for i, m in enumerate(msgs):
            if type(m).__name__ != "ToolMessage":
                continue
            prev = msgs[i - 1] if i else None
            if not getattr(prev, "tool_calls", None):
                return False
            if prev.tool_calls[0].get("id") != m.tool_call_id:
                return False
        return True

    check("A6 装配降级后 tool 配对完整（无孤儿 ToolMessage）",
          _paired(view) and sessions._est_tokens(view) < sessions._est_tokens(big),
          f"{len(big)} 条 / token {sessions._est_tokens(big)} -> {sessions._est_tokens(view)}，命中 {level}")

    # --- A7 草稿原子消费 ---
    sid_d = "m1test-draft"
    did = store.create_draft(sid_d, 1001, {"cart_id": 7, "address_id": 3, "pay_amount": 9.9})
    first = store.pop_draft(sid_d, 1001, did)
    second = store.pop_draft(sid_d, 1001, did)
    check("A7 草稿一次消费：第一次拿到、第二次拿到 None",
          first is not None and first.get("cart_id") == 7 and second is None)

    # --- A8 并发消费同一草稿：只有一个成功 ---
    did2 = store.create_draft(sid_d, 1001, {"cart_id": 8})
    results = []
    lock = threading.Lock()

    def _pop():
        r = store.pop_draft(sid_d, 1001, did2)
        with lock:
            results.append(r)

    threads = [threading.Thread(target=_pop) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wins = [r for r in results if r is not None]
    check("A8 并发 8 次抢同一草稿，仅 1 次成功", len(wins) == 1, f"成功 {len(wins)} 次")

    # --- A9 草稿归属：换会员拿不到 ---
    did3 = store.create_draft(sid_d, 1001, {"cart_id": 9})
    check("A9 草稿归属：他会员 pop 得到 None",
          store.pop_draft(sid_d, 8888, did3) is None)
    store.pop_draft(sid_d, 1001, did3)  # 清理

    # --- A10 幂等结果回放 ---
    store.remember_result("m1test-replay", 123456)
    check("A10 结果回放命中同一 orderId",
          store.recall_result("m1test-replay") == 123456)
    check("A11 未记录的草稿回放返回 None",
          store.recall_result("m1test-nonexistent") is None)

    # 清理
    store.clear_session(sid_d)
    store.client().delete(store._k_result("m1test-replay"))
    store.clear_session(sid_b)


# ============================================================ Part B 双实例


def start_server(port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    p = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if r.status == 200:
                    return p
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    p.kill()
    raise RuntimeError(f"服务 {port} 未在预期时间内就绪")


def kill_server(p: subprocess.Popen) -> None:
    """连子进程一起杀（uvicorn 可能再 fork）。"""
    if p.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                       capture_output=True, check=False)
    else:  # pragma: no cover
        p.terminate()
    try:
        p.wait(timeout=15)
    except subprocess.TimeoutExpired:  # pragma: no cover
        p.kill()


def get_history(port: int, sid: str, token: str | None = None, member_id=None) -> list:
    url = f"http://127.0.0.1:{port}/api/chat/history?session_id={sid}"
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8")).get("messages", [])


def part_b_two_instances():
    print("\n===== Part B：两个独立服务进程（共享 Redis，验证重启续聊 / 不串会话）=====")
    P1, P2 = 8091, 8092
    if not free_ports_ok(P1, P2):
        check(f"端口 {P1}/{P2} 可用", False, "被占用，跳过 Part B")
        return

    sid = "m1test-http"
    store.clear_session(sid)
    sessions.reset_history(sid, [HumanMessage(content="上一句我说了暗号：芝麻开门")], member_id=1001)

    srv1 = start_server(P1)
    srv2 = start_server(P2)
    try:
        h1 = get_history(P1, sid)
        h2 = get_history(P2, sid)
        check("B1 会话在服务进程外：两个实例都读得到",
              len(h1) == 1 and h1 == h2, f"实例1 {len(h1)} 条 / 实例2 {len(h2)} 条")

        # 不串会话：另一个 sid 写别的内容，两边仍各读各的
        sid2 = "m1test-http-2"
        store.clear_session(sid2)
        sessions.reset_history(sid2, [HumanMessage(content="另一个会话的内容")], member_id=2002)
        check("B2 不串会话：两个 sid 各自独立",
              get_history(P1, sid)[0]["content"] != get_history(P2, sid2)[0]["content"]
              and get_history(P2, sid2)[0]["content"] == "另一个会话的内容")
        store.clear_session(sid2)

        # 重启：杀掉实例1，重启后仍能续聊
        kill_server(srv1)
        time.sleep(1)
        srv1 = start_server(P1)
        after = get_history(P1, sid)
        check("B3 服务重启后会话仍在（可续聊）",
              len(after) == 1 and "芝麻开门" in after[0]["content"],
              f"重启后读回 {len(after)} 条")
    finally:
        kill_server(srv1)
        kill_server(srv2)
        store.clear_session(sid)


if __name__ == "__main__":
    store.assert_available()
    print(f"Redis: {store._mask(store.config.REDIS_URL)}")
    part_a_state_layer()
    part_b_two_instances()
    print(f"\n===== 结果：{PASS} 通过 / {FAIL} 失败 =====")
    sys.exit(1 if FAIL else 0)
