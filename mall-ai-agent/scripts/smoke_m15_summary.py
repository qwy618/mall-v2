"""M1.5.3 验收：T3 历史摘要（分段链 + 惰性异步 + 可回滚）。

覆盖的硬指标：
  S1 分段生成：热区之外的旧轮被压成段，digest 与源区间一致
  S2 装配注入：摘要以**明确标注的「背景记忆」system 消息**注入，绝不伪装成用户发言
  S3 人工回滚：删掉摘要键后装配自动退回 T2（功能不受影响、原文毫发无损）
  S4 校验回滚：索引/段不一致、或**源区间内容变了** → 该段被跳过（不注入过期摘要）
  S5 压缩失败：LLM 报错 → 不写索引（等于没压过），会话照常，原文条数不变
  S6 单飞锁：同一会话同时只有一个压缩任务；只有持有者能释放
  S7 分段链滚压：段数超阈值时最旧的若干段被滚压成更高层的一段
  S8 事实源只增不减：全程 messages 条数不变
  S9（可选）真实 LLM：非空中文摘要 + 注入成功

默认**离线**（用假摘要器替换 summarize._ask），毫秒级；
加 M15S_LLM=1 追加真实 DeepSeek 校验。

运行：.venv\\Scripts\\python scripts/smoke_m15_summary.py
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402

from app import config, sessions, store, summarize  # noqa: E402

PASS = 0
FAIL = 0
MEMBER = 7002
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


def bg_messages(view):
    """视图里的「背景记忆」system 消息。"""
    return [m for m in view
            if type(m).__name__ == "SystemMessage"
            and isinstance(getattr(m, "content", None), str)
            and m.content.startswith("【背景记忆")]


def wait_lock_released(sid: str, timeout: float = 10.0) -> bool:
    """轮询等待后台任务释放单飞锁（daemon 线程结束）。"""
    end = time.time() + timeout
    while time.time() < end:
        if not store.client().exists(store._k_summary_lock(sid)):
            return True
        time.sleep(0.05)
    return False


def fake_ask_factory():
    def _fake(system: str, user: str, tag: str) -> str:
        return f"（{tag}）要点：本段共 {len(user)} 字的历史对话"
    return _fake


# ---------------------------------------------------------------- 各用例

def part_s1_s2(sid: str):
    print("\n===== S1/S2：分段生成 + 装配注入形态 =====")
    store.clear_session(sid)
    sessions.reset_history(sid, make_rounds(20), MEMBER)
    n0 = store.count_messages(sid)

    real_ask = summarize._ask
    summarize._ask = fake_ask_factory()
    try:
        made = summarize.run_once(sid, MEMBER)
    finally:
        summarize._ask = real_ask

    index = store.load_summary_index(sid)
    seg_rounds = config.SUMMARY_SEG_ROUNDS
    # 20 轮 - 热区 6 = 14 可压 → 14//8 = 1 段
    expect = max(0, 20 - sessions.HOT_ROUNDS) // seg_rounds
    check("S1a 分段生成数量正确", made == expect and len(index) == expect,
          f"新压 {made} 段 / 索引 {len(index)} 段（期望 {expect}）")

    stored = sessions.get_history(sid, MEMBER)
    spans = sessions.round_spans(stored)
    seg0 = store.load_segment(sid, min(index)) if index else None
    if seg0:
        want = sessions.digest_msg(stored[spans[0][0]:spans[seg_rounds - 1][1]])
        check("S1b 段覆盖区间与 digest 与源一致",
              seg0["rFrom"] == 0 and seg0["rTo"] == seg_rounds
              and seg0["mFrom"] == spans[0][0] and seg0["mTo"] == spans[seg_rounds - 1][1]
              and seg0["digest"] == want,
              f"第0~{seg0['rTo']}轮, digest={seg0['digest'][:8]}")
    else:
        check("S1b 段覆盖区间与 digest 与源一致", False, "没有段")
    check("S1c 覆盖进度写入 meta", store.session_summary_rounds(sid) == seg_rounds,
          f"summRounds={store.session_summary_rounds(sid)}")

    # S2 极小预算 → T3 → 注入背景记忆（SystemMessage），且不伪装成 User
    keep = sessions.TOKEN_BUDGET
    sessions.TOKEN_BUDGET = 1
    view, lv = sessions._assemble(sid, stored, [HumanMessage(content="再来")])
    sessions.TOKEN_BUDGET = keep
    bgs = bg_messages(view)
    fake_human = [m for m in view if type(m).__name__ == "HumanMessage"
                  and isinstance(m.content, str) and "背景记忆" in m.content]
    check("S2a 命中 T3 且注入了「背景记忆」system 消息",
          lv == "T3" and len(bgs) == 1, f"level={lv} bg={len(bgs)}")
    check("S2b 背景记忆含摘要正文、且绝不伪装成用户发言",
          bool(bgs) and "要点：" in bgs[0].content and "非用户原话" in bgs[0].content
          and not fake_human,
          f"伪装成用户的消息 {len(fake_human)} 条")
    check("S2c 注入后 tool 配对仍完整", paired(view))

    # 诊断键记录注入段数（诊断写在 assemble_history 里，故走它一次）
    keep = sessions.TOKEN_BUDGET
    sessions.TOKEN_BUDGET = 1
    sessions.assemble_history(sid, MEMBER, [HumanMessage(content="再来")])
    sessions.TOKEN_BUDGET = keep
    info = store.load_assembly(sid)
    check("S2d 装配诊断记录 T3 注入段数", info.get("level") == "T3"
          and info.get("segments") == expect, json.dumps(info, ensure_ascii=False))

    check("S8 事实源只增不减（装配/压缩不改原文）", store.count_messages(sid) == n0,
          f"{n0} 条")
    return expect


def part_s3(sid: str):
    print("\n===== S3：人工回滚（删摘要 → 退回 T2）=====")
    before = store.count_messages(sid)
    store.clear_summaries(sid)
    check("S3a 删摘要后索引为空且覆盖进度归零",
          len(store.load_summary_index(sid)) == 0
          and store.session_summary_rounds(sid) == 0)

    stored = sessions.get_history(sid, MEMBER)
    keep = sessions.TOKEN_BUDGET
    sessions.TOKEN_BUDGET = 1
    view, lv = sessions._assemble(sid, stored, [HumanMessage(content="再来")])
    sessions.TOKEN_BUDGET = keep
    check("S3b 回滚后 T3 不再注入（等同稍长上下文，功能不受影响）",
          lv == "T3" and not bg_messages(view) and paired(view),
          f"level={lv} 视图 {len(view)} 条")
    check("S3c 回滚不影响事实源", store.count_messages(sid) == before)


def part_s4(sid: str):
    print("\n===== S4：校验回滚（索引不一致 / 源变了 → 跳过该段）=====")
    real_ask = summarize._ask
    summarize._ask = fake_ask_factory()
    try:
        summarize.run_once(sid, MEMBER)
    finally:
        summarize._ask = real_ask
    stored = sessions.get_history(sid, MEMBER)
    check("S4a 重新压出可注入的段", len(sessions.verified_segments(sid, stored)) >= 1)

    # (a) 伪造一条"索引与段 digest 不一致"的记录 → 必须被跳过
    store.client().hset(store._k_summary_index(sid), "999",
                        json.dumps({"digest": "bad", "rFrom": 0, "rTo": 8,
                                    "mFrom": 0, "mTo": 16}, ensure_ascii=False))
    store.save_segment(sid, 999, {"seg": 999, "level": 1, "rFrom": 0, "rTo": 8,
                                  "mFrom": 0, "mTo": 16, "digest": "other",
                                  "text": "伪造段", "ts": 0})
    segs = sessions.verified_segments(sid, stored)
    check("S4b 索引/段 digest 不一致的段被跳过",
          all(s.get("seg") != 999 for s in segs), f"可信段 {len(segs)} 个")

    # (b) 源区间内容变过 → digest 不匹配 → 段失效（不再注入过期摘要）
    tampered = sessions.get_history(sid, MEMBER)
    tampered[0] = HumanMessage(content="（这轮被改过）")   # 落在第 0 段覆盖区间内，且不破坏 tool 配对
    sessions.reset_history(sid, tampered, MEMBER)
    stored2 = sessions.get_history(sid, MEMBER)
    check("S4c 源区间内容变化 → 摘要段失效（跳过，退回上一级）",
          len(sessions.verified_segments(sid, stored2)) == 0)

    keep = sessions.TOKEN_BUDGET
    sessions.TOKEN_BUDGET = 1
    view, lv = sessions._assemble(sid, stored2, [HumanMessage(content="再来")])
    sessions.TOKEN_BUDGET = keep
    check("S4d 失效后不再注入背景记忆", lv == "T3" and not bg_messages(view) and paired(view))


def part_s5(sid: str):
    print("\n===== S5：压缩失败不写索引 =====")
    store.clear_session(sid)
    sessions.reset_history(sid, make_rounds(20), MEMBER)
    n0 = store.count_messages(sid)

    def fail_ask(system: str, user: str, tag: str):
        # 真实 _ask 会吞掉异常并返回 None（见 app/summarize.py）；这里等价模拟"压缩失败"
        return None

    real_ask = summarize._ask
    summarize._ask = fail_ask
    try:
        made = summarize.run_once(sid, MEMBER)
    finally:
        summarize._ask = real_ask
    check("S5a 压缩失败 → 不写任何段（等于没压过）",
          made == 0 and len(store.load_summary_index(sid)) == 0)
    check("S5b 压缩失败不崩、原文条数不变",
          store.count_messages(sid) == n0 and store.session_summary_rounds(sid) == 0)

    # 真实 _ask 的容错：底层 LLM 抛错必须被吞掉（返回 None），绝不上抛到对话链路
    def bad_llm(*_a, **_k):
        raise RuntimeError("模拟 LLM 建连失败")

    real_get = summarize.get_llm
    summarize.get_llm = bad_llm
    try:
        out = summarize._ask("s", "u", "test")
    finally:
        summarize.get_llm = real_get
    check("S5c 底层 LLM 抛错被 _ask 吞掉（返回 None，不上抛）", out is None)


def part_s6():
    print("\n===== S6：单飞锁 =====")
    sid = "m15test-lock"
    store.client().delete(store._k_summary_lock(sid))
    a, b = "tok-a", "tok-b"
    check("S6a 首个持有者可抢到", store.acquire_summary_lock(sid, a))
    check("S6b 第二个抢不到（已有任务在跑）", not store.acquire_summary_lock(sid, b))
    store.release_summary_lock(sid, b)             # 非持有者释放无效
    check("S6c 非持有者释放无效", store.client().get(store._k_summary_lock(sid)) == a)
    store.release_summary_lock(sid, a)
    check("S6d 持有者释放成功", not store.client().exists(store._k_summary_lock(sid)))
    store.client().delete(store._k_summary_lock(sid))


def part_s7(sid: str):
    print("\n===== S7：分段链滚压 =====")
    store.clear_session(sid)
    sessions.reset_history(sid, make_rounds(40), MEMBER)
    keep_roll, keep_max = config.SUMMARY_ROLLUP_SEGS, config.SUMMARY_MAX_NEW_SEGS
    config.SUMMARY_ROLLUP_SEGS, config.SUMMARY_MAX_NEW_SEGS = 2, 100
    real_ask = summarize._ask
    summarize._ask = fake_ask_factory()
    try:
        summarize.run_once(sid, MEMBER)
    finally:
        summarize._ask = real_ask
        config.SUMMARY_ROLLUP_SEGS, config.SUMMARY_MAX_NEW_SEGS = keep_roll, keep_max

    index = store.load_summary_index(sid)
    seg_rounds = config.SUMMARY_SEG_ROUNDS
    complete = max(0, 40 - sessions.HOT_ROUNDS) // seg_rounds      # (40-6)//8 = 4
    covered_to = max((s.get("rTo", 0) for s in index.values()), default=0)
    levels = sorted({s.get("level") for s in index.values()})
    check("S7a 段数被滚压到阈值以内", len(index) <= 2, f"{len(index)} 段")
    check("S7b 滚压后仍连续覆盖 [0, 可压轮数)",
          min((s.get("rFrom", 9e9) for s in index.values()), default=-1) == 0
          and covered_to == complete * seg_rounds,
          f"覆盖到第 {covered_to} 轮（期望 {complete * seg_rounds}）")
    check("S7c 产生更高层段（level>1）", max(levels or [0]) >= 2, f"levels={levels}")
    check("S8(复) 滚压不改事实源", store.count_messages(sid) == 160,
          f"{store.count_messages(sid)} 条")


def part_s10(sid: str):
    print("\n===== S10：惰性异步调度 =====")
    store.clear_session(sid)
    sessions.reset_history(sid, make_rounds(4), MEMBER)
    store.set_session_rounds(sid, 4)
    store.set_session_summary_rounds(sid, 0)
    check("S10a 轮数不足 → 不投递任务（省一次无谓线程）",
          summarize.maybe_schedule(sid, MEMBER) is False)

    # 攒够 + 超预算 → 投递；后台线程离线用假摘要器
    sessions.reset_history(sid, make_rounds(20), MEMBER)   # reset 会写 rounds=20
    store.client().set(store._k_assembly(sid),
                       json.dumps({"level": "T3"}, ensure_ascii=False), ex=60)
    real_ask = summarize._ask
    summarize._ask = fake_ask_factory()
    try:
        scheduled = summarize.maybe_schedule(sid, MEMBER)
        ok_join = wait_lock_released(sid)
    finally:
        summarize._ask = real_ask
    check("S10b 超预算+攒够段 → 投递后台任务且不阻塞", scheduled is True)
    check("S10c 后台任务完成并释放单飞锁", ok_join)
    check("S10d 异步压缩真的产出了段", len(store.load_summary_index(sid)) >= 1,
          f"{len(store.load_summary_index(sid))} 段")


def part_s9_llm(sid: str):
    print("\n===== S9：真实 LLM 压缩（可选）=====")
    store.clear_session(sid)
    sessions.reset_history(sid, make_rounds(20), MEMBER)
    made = summarize.run_once(sid, MEMBER)
    index = store.load_summary_index(sid)
    seg = store.load_segment(sid, min(index)) if index else None
    text = (seg or {}).get("text", "")
    check("S9a 真实 LLM 压出非空摘要", made >= 1 and len(text) >= 8,
          f"摘要={text[:40]}…")
    stored = sessions.get_history(sid, MEMBER)
    check("S9b 真实摘要通过 digest 校验", len(sessions.verified_segments(sid, stored)) >= 1)
    keep = sessions.TOKEN_BUDGET
    sessions.TOKEN_BUDGET = 1
    view, lv = sessions._assemble(sid, stored, [HumanMessage(content="再来")])
    sessions.TOKEN_BUDGET = keep
    check("S9c 真实摘要可注入且 tool 配对完整", lv == "T3" and bg_messages(view) and paired(view))


if __name__ == "__main__":
    store.assert_available()
    print(f"Redis: {store._mask(store.config.REDIS_URL)}")
    sid = "m15test-summary"
    try:
        part_s1_s2(sid)
        part_s3(sid)
        part_s4(sid)
        part_s5(sid)
        part_s6()
        part_s7(sid)
        part_s10(sid)
        if os.getenv("M15S_LLM") == "1":
            part_s9_llm(sid)
    finally:
        store.clear_session(sid)
        store.client().delete(store._k_summary_lock(sid))
    print(f"\n===== 结果：{PASS} 通过 / {FAIL} 失败 =====")
    sys.exit(1 if FAIL else 0)
