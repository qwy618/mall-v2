"""M1.5.4 验收：单会话上限裁剪 + token 精算。

覆盖的硬指标：
  R1 字节计量：追加 / 重置 / 裁剪都让 meta.bytes 与真实载荷一致
  R2 未覆盖不删：超上限但尚无摘要覆盖 → 拒绝删除（宁可先超限，绝不丢唯一记录）
  R3 达上限才删最旧：被删的轮**全部落在已摘要覆盖的前缀内**
  R4 裁剪后摘要仍可注入：轮号校验不因下标前移而误判失效（pruned → 信任）
  R5 审计留痕：ai:retention:{sid}:last 记下删了哪几轮、由哪些摘要段兜底
  R6 只增不减（除裁剪）：未超限时事实源条数严格不降
  R7 字节上限独立生效：轮数没超、字节超了 → 同样会裁
  R8 token 精算：中文不再低估、英文 JSON 不再高估（比 len//2 更贴近真实）
  R9 trimmedRounds 语义：在库轮数 = rounds - trimmedRounds

默认**离线**（假摘要器），毫秒级；不需要 LLM，也不起 HTTP 服务。
运行：.venv\\Scripts\\python scripts/smoke_m15_retention.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402

from app import config, sessions, store, summarize  # noqa: E402

PASS = 0
FAIL = 0
MEMBER = 7003
PIC = "http://oss.example.com/" + "x" * 400


def check(name: str, ok: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")
    return ok


def paired(msgs) -> bool:
    for i, m in enumerate(msgs):
        if type(m).__name__ != "ToolMessage":
            continue
        prev = msgs[i - 1] if i else None
        if not getattr(prev, "tool_calls", None):
            return False
        if prev.tool_calls[0].get("id") != m.tool_call_id:
            return False
    return True


def search_round(i: int, items: int = 3):
    """一轮 4 条消息（提问 → 调工具 → 大 JSON → 回答）。"""
    data = [{"id": 100 + i * 10 + k, "name": f"耳机{i}-{k}", "price": 199 + k,
             "pic": PIC, "productSn": f"SN{i}{k}", "sale": 88}
            for k in range(items)]
    return [
        HumanMessage(content=f"第{i}轮：帮我找降噪耳机"),
        AIMessage(content="", tool_calls=[{"name": "search_products",
                                          "args": {"keyword": "降噪耳机"}, "id": f"c{i}"}]),
        ToolMessage(content=json.dumps(data, ensure_ascii=False),
                    tool_call_id=f"c{i}", name="search_products"),
        AIMessage(content=f"第{i}轮：为你找到 {items} 款"),
    ]


def make_rounds(n: int):
    return [m for i in range(n) for m in search_round(i)]


def fake_ask_factory():
    def _fake(system: str, user: str, tag: str) -> str:
        return f"（{tag}）要点：本段共 {len(user)} 字的历史对话"
    return _fake


def bg_messages(view):
    return [m for m in view
            if type(m).__name__ == "SystemMessage"
            and isinstance(getattr(m, "content", None), str)
            and m.content.startswith("【背景记忆")]


def with_limits(max_rounds: int, max_bytes: int):
    """临时改上限，返回还原函数。"""
    keep = (config.SESSION_MAX_ROUNDS, config.SESSION_MAX_BYTES)
    config.SESSION_MAX_ROUNDS, config.SESSION_MAX_BYTES = max_rounds, max_bytes
    return lambda: setattr(config, "SESSION_MAX_ROUNDS", keep[0]) or \
        setattr(config, "SESSION_MAX_BYTES", keep[1])


# ---------------------------------------------------------------- R1

def part_r1_bytes():
    print("\n===== R1：字节计量与裁剪扣减 =====")
    sid = "m15test-bytes"
    store.clear_session(sid)
    sessions.reset_history(sid, make_rounds(3), MEMBER)          # 12 条
    real = store._payload_bytes_raw(store._k_messages(sid))
    check("R1a 追加后 meta.bytes == 真实载荷字节",
          store.session_bytes(sid) == real, f"meta={store.session_bytes(sid)} real={real}")

    sessions.append_turn(sid, [HumanMessage(content="补充一句"), AIMessage(content="好的")], MEMBER)
    real2 = store._payload_bytes_raw(store._k_messages(sid))
    check("R1b 再追加后仍一致（增量准确）",
          store.session_bytes(sid) == real2, f"meta={store.session_bytes(sid)} real={real2}")

    store.trim_oldest_messages(sid, 4)                           # 删一整轮
    real3 = store._payload_bytes_raw(store._k_messages(sid))
    check("R1c 裁剪后字节精确扣减（不漂移）",
          store.session_bytes(sid) == real3 and real3 < real2,
          f"meta={store.session_bytes(sid)} real={real3}")

    sessions.reset_history(sid, make_rounds(2), MEMBER)
    check("R1d 重置后字节重算、trimmedRounds 归零",
          store.session_bytes(sid) == store._payload_bytes_raw(store._k_messages(sid))
          and store.session_trimmed_rounds(sid) == 0)
    store.clear_session(sid)


# ---------------------------------------------------------------- R2 / R3

def part_r2_r3():
    print("\n===== R2/R3：未覆盖不删 → 覆盖后才删 =====")
    sid = "m15test-retention"
    store.clear_session(sid)
    sessions.reset_history(sid, make_rounds(20), MEMBER)          # 80 条, 20 轮
    n0 = store.count_messages(sid)

    restore = with_limits(12, 0)
    try:
        # R2：尚无任何摘要覆盖 → 拒绝删除
        audit0 = summarize.maybe_trim(sid, MEMBER)
        check("R2 超上限但无摘要覆盖 → 拒绝删除（只记录 blocked）",
              audit0.get("blocked") is True and store.count_messages(sid) == n0,
              f"audit={audit0} 条数={store.count_messages(sid)}")

        # 造摘要覆盖：20 轮 - 热区 6 = 14 可压 → 14//8 = 1 段，覆盖 [0,8)
        real_ask = summarize._ask
        summarize._ask = fake_ask_factory()
        try:
            summarize.run_once(sid, MEMBER)
        finally:
            summarize._ask = real_ask
        covered = store.session_summary_rounds(sid)
        check("R3a 摘要覆盖前缀已就绪", covered == config.SUMMARY_SEG_ROUNDS,
              f"summRounds={covered}")

        # R3：达上限 → 删最旧，且删的轮全在覆盖内
        audit = summarize.maybe_trim(sid, MEMBER)
        after = store.count_messages(sid)
        check("R3b 删掉最旧的 8 轮（32 条），落在已覆盖前缀内",
              audit.get("trimmedRounds") == 8 and audit.get("fromRound") == 0
              and audit.get("toRound") == 8 and n0 - after == 32
              and audit["toRound"] <= covered,
              f"audit={json.dumps(audit, ensure_ascii=False)}")

        rounds, trimmed = store.session_rounds(sid), store.session_trimmed_rounds(sid)
        check("R3c trimmedRounds 与在库轮数自洽（present = rounds - trimmed）",
              trimmed == 8 and max(0, rounds - trimmed) <= 12,
              f"rounds={rounds} trimmed={trimmed} present={rounds - trimmed}")

        # 剩下的最旧一轮应是"第8轮"（前 8 轮已被删）
        stored = sessions.get_history(sid, MEMBER)
        spans = sessions.round_spans(stored)
        first_human = next(m.content for m in stored if type(m).__name__ == "HumanMessage")
        check("R3d 删的是最旧的整轮（在库首轮为第 8 轮）",
              len(spans) == 12 and first_human.startswith("第8轮"), first_human)

        # R4：裁剪后摘要仍可注入（轮号校验不漂移）
        segs = sessions.verified_segments(sid, stored)
        keep = sessions.TOKEN_BUDGET
        sessions.TOKEN_BUDGET = 1
        view, lv = sessions._assemble(sid, stored, [HumanMessage(content="再来")])
        sessions.TOKEN_BUDGET = keep
        bgs = bg_messages(view)
        check("R4a 源轮已被裁剪的段未被误判失效（pruned → 信任）",
              len(segs) == 1 and segs[0].get("rTo") == 8, f"可信段 {len(segs)}")
        check("R4b 裁剪后 T3 仍注入「背景记忆」且 tool 配对完整",
              lv == "T3" and len(bgs) == 1 and paired(view))

        # R5：审计留痕
        rec = store.load_retention(sid)
        check("R5 审计键记录了删除范围与兜底段",
              rec.get("trimmedRounds") == 8 and rec.get("coveredBy"),
              json.dumps(rec, ensure_ascii=False))

        # R6：本轮不再超限 → 再调也不删（只增不减）
        again = summarize.maybe_trim(sid, MEMBER)
        check("R6 未超限时不再裁剪（幂等，事实源只增不减）",
              again == {} and store.count_messages(sid) == after)
    finally:
        restore()
        store.clear_session(sid)


# ---------------------------------------------------------------- R7

def part_r7_bytes_limit():
    print("\n===== R7：字节上限独立生效 =====")
    sid = "m15test-bytecap"
    store.clear_session(sid)
    sessions.reset_history(sid, make_rounds(20), MEMBER)
    n0 = store.count_messages(sid)

    real_ask = summarize._ask
    summarize._ask = fake_ask_factory()
    try:
        summarize.run_once(sid, MEMBER)
    finally:
        summarize._ask = real_ask

    restore = with_limits(0, 8000)          # 关闭轮数上限，只留很小的字节上限
    try:
        audit = summarize.maybe_trim(sid, MEMBER)
        check("R7 轮数没超、字节超 → 仍按已覆盖前缀裁剪",
              audit.get("trimmedRounds", 0) >= 1
              and store.count_messages(sid) < n0
              and audit["toRound"] <= store.session_summary_rounds(sid),
              json.dumps(audit, ensure_ascii=False))
    finally:
        restore()
        store.clear_session(sid)


# ---------------------------------------------------------------- R8

def part_r8_token_estimate():
    print("\n===== R8：token 精算（vs 旧的 len//2）=====")
    # 中文：旧法 len//2 只有 ~0.5 token/字，**低估**一半
    zh = "降噪耳机" * 100                                     # 400 字
    est_zh = sessions._est_text(zh)
    check("R8a 中文不再低估（≈1 token/字，旧法仅 0.5）",
          est_zh >= len(zh) * 0.9 and est_zh > len(zh) // 2 * 1.5,
          f"len={len(zh)} 旧={len(zh)//2} 新={est_zh}")

    # 英文/JSON：旧法按 2 字符/token，**高估**约 1.6 倍
    en = json.dumps([{"id": i, "name": "noise cancelling earphone", "price": 199,
                      "desc": "bluetooth 5.3 long battery life"} for i in range(40)])
    est_en = sessions._est_text(en)
    check("R8b 英文 JSON 不再高估（≈3.3 字符/token，旧法按 2）",
          est_en < len(en) // 2 and est_en > len(en) / 6,
          f"len={len(en)} 旧={len(en)//2} 新={est_en}")

    # 混合（真实工具消息：中文 + 长 URL/JSON）仍落在合理区间
    mixed = search_round(0)[2].content
    est_m = sessions._est_text(mixed)
    check("R8c 混合内容估算落在合理区间",
          len(mixed) / 6 < est_m < len(mixed), f"len={len(mixed)} 新={est_m}")


# ---------------------------------------------------------------- R9

def part_r9_rounds_semantics():
    print("\n===== R9：trimmedRounds 语义 =====")
    sid = "m15test-rounds"
    store.clear_session(sid)
    sessions.reset_history(sid, make_rounds(3), MEMBER)
    check("R9a 重置后 rounds == 实际轮数、trimmed == 0",
          store.session_rounds(sid) == 3 and store.session_trimmed_rounds(sid) == 0,
          f"rounds={store.session_rounds(sid)}")

    store.trim_oldest_messages(sid, 4, trimmed_rounds_delta=1)
    stored = sessions.get_history(sid, MEMBER)
    check("R9b 裁剪一轮后：rounds 不动、trimmed=1、在库 2 轮",
          store.session_rounds(sid) == 3 and store.session_trimmed_rounds(sid) == 1
          and len(sessions.round_spans(stored)) == 2,
          f"rounds={store.session_rounds(sid)} trimmed={store.session_trimmed_rounds(sid)}")
    store.clear_session(sid)


if __name__ == "__main__":
    store.assert_available()
    print(f"Redis: {store._mask(store.config.REDIS_URL)}")
    part_r1_bytes()
    part_r2_r3()
    part_r7_bytes_limit()
    part_r8_token_estimate()
    part_r9_rounds_semantics()
    print(f"\n===== 结果：{PASS} 通过 / {FAIL} 失败 =====")
    sys.exit(1 if FAIL else 0)
