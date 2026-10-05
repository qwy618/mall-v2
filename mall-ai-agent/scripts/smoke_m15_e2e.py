"""M1.5 端到端验收：读写分离在**真实 LLM** 下的正确性。

只验证一件最要命的事：**"agent 返回的完整状态 = 我发出去的装配视图 + 本轮新增"**。
读写分离全靠这个假设——写路径只追加 `result[len(sent):]`，若假设不成立，
历史会被写重（重复消息）或写丢（对话失去上下文）。

用两轮真实对话证明：
  ① 第一轮"自我介绍" → 存储里**恰好**是 用户问 + 助手答 两条（不多不少）
  ② 第二轮问"我叫什么" → 助手答得出，证明上一轮确实进了上下文（装配链路通）

成本：2 次 LLM 调用。运行：.venv\\Scripts\\python scripts/smoke_m15_e2e.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402

from app import sessions, store, summarize  # noqa: E402
from app.agent import build_agent  # noqa: E402
from app.main import _delta  # noqa: E402
from app.tools.order_tools import current_member, current_session, current_token  # noqa: E402

PASS = 0
FAIL = 0
SID = "m15e2e"


def check(name: str, ok: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")
    return ok


def run_turn(agent, message: str, sid: str = SID) -> str:
    """完全复刻 main.py 的读写路径。"""
    sent, n_stored = sessions.assemble_history(sid, None, [HumanMessage(content=message)])
    tok = current_token.set(None)
    ses = current_session.set(sid)
    mem = current_member.set(None)
    try:
        result = agent.invoke({"messages": sent})
    finally:
        current_token.reset(tok)
        current_session.reset(ses)
        current_member.reset(mem)
    reply = result["messages"][-1].content
    sessions.append_turn(sid, _delta(result.get("messages") or [], n_stored), None)
    summarize.maybe_trim(sid)          # M1.5.4：默认上限 300 轮，短会话应为 no-op
    return reply



if __name__ == "__main__":
    store.assert_available()
    print(f"Redis: {store._mask(store.config.REDIS_URL)}")
    store.clear_session(SID)
    agent = build_agent()

    print("\n===== 第 1 轮：自我介绍（期望入库恰好 2 条）=====")
    r1 = run_turn(agent, "你好，我叫小明，随便聊聊就好，不用推荐商品")
    n1 = store.count_messages(SID)
    msgs = sessions.get_history(SID, None)
    print(f"  助手：{r1[:60]}")
    check("T1 本轮只追加 2 条（用户问 + 助手答）", n1 == 2, f"实际 {n1} 条")
    check("T2 入库内容与所见一致",
          len(msgs) == 2 and msgs[0].content.startswith("你好，我叫小明")
          and msgs[1].content == r1,
          f"[{msgs[0].content[:16]}...] / [{msgs[1].content[:16]}...]")

    print("\n===== 第 2 轮：追问（期望答得出名字 → 上文确实进了上下文）=====")
    r2 = run_turn(agent, "我刚才说我叫什么名字？只回答名字")
    n2 = store.count_messages(SID)
    print(f"  助手：{r2[:60]}")
    check("T3 第二轮又追加 2 条（累计 4 条，无重复无丢失）", n2 == 4, f"实际 {n2} 条")
    check("T4 助手能说出上一轮的名字（跨轮上下文有效）", "小明" in r2, f"回复={r2[:40]}")
    check("T5 装配级别为 T0（短会话无需压缩）",
          store.load_assembly(SID).get("level") == "T0",
          json.dumps(store.load_assembly(SID), ensure_ascii=False))

    store.clear_session(SID)

    # ================= T3：背景记忆进入真实 LLM 调用 =================
    # 目的：证明"中段注入的 system 消息"被 DeepSeek 接受（不少兼容实现只容忍首条 system），
    # 且 LLM 真的读了它。摘要用离线假压缩器生成，本部分只花 1 次 LLM 调用（对话本身）。
    print("\n===== 第 3 部分：T3 背景记忆 + 真实 LLM =====")
    sid3 = "m15e2e-t3"
    store.clear_session(sid3)
    rounds = []
    for i in range(20):
        rounds += [
            HumanMessage(content=f"第{i}轮：帮我找降噪耳机，预算 500 以内"),
            AIMessage(content="", tool_calls=[{"name": "search_products",
                                              "args": {"keyword": "降噪耳机"}, "id": f"c{i}"}]),
            ToolMessage(content=json.dumps(
                [{"id": 200 + i, "name": f"降噪耳机{i}", "price": 299, "pic": "http://oss/" + "x" * 300}],
                ensure_ascii=False), tool_call_id=f"c{i}", name="search_products"),
            AIMessage(content=f"第{i}轮：为你找到 1 款"),
        ]
    sessions.reset_history(sid3, rounds, None)

    real_ask = summarize._ask
    summarize._ask = lambda s, u, t: "用户一直在找降噪耳机，预算 500 元以内。"
    try:
        summarize.run_once(sid3, None)
    finally:
        summarize._ask = real_ask

    keep = sessions.TOKEN_BUDGET
    sessions.TOKEN_BUDGET = 1                       # 逼到 T3
    sent, _n = sessions.assemble_history(sid3, None, [HumanMessage(content="根据背景记忆，我在找什么商品？一句话回答")])
    sessions.TOKEN_BUDGET = keep
    bgs = [m for m in sent if type(m).__name__ == "SystemMessage"
           and isinstance(m.content, str) and m.content.startswith("【背景记忆")]
    check("T6 T3 装配注入了「背景记忆」system 消息", len(bgs) == 1, f"bg={len(bgs)}")

    r3 = run_turn(agent, "根据背景记忆，我在找什么商品？一句话回答", sid=sid3)
    print(f"  助手：{r3[:70]}")
    check("T7 LLM 接受中段 system 消息（调用成功且回复非空）", bool(r3 and r3.strip()))
    check("T8 回复体现了背景记忆里的偏好（耳机）", "耳机" in r3, f"回复={r3[:40]}")
    n3 = store.count_messages(sid3)
    check("T9 事实源只增不减，且没有把压缩视图写回（只追加 delta）",
          len(rounds) + 2 <= n3 <= len(rounds) + 10,
          f"{len(rounds)} -> {n3} 条")

    store.clear_session(sid3)
    print(f"\n===== 结果：{PASS} 通过 / {FAIL} 失败 =====")
    sys.exit(1 if FAIL else 0)
