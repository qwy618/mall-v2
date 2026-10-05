"""M1.5 验收：长对话装配（存储与装配分离）。

覆盖三条硬指标（不需要 LLM，也不起 HTTP 服务）：
  ① **存量迁移**：旧的 String(JSON 数组) 会话键 → List，透明且幂等
  ② **事实源只增不减**：装配（压缩）只发生在"读"，绝不写回存储
  ③ **分级降级**：T0 原样 / T1 工具结果标记化 / T2 中间轮折叠，且
     - 桩保留 id/名称/价格（指代不断链）
     - 折叠保头部 + 最近轮，且**含未消费草稿的轮永不被折叠**
     - 任何一级都**不破坏 tool 配对**（无孤儿 ToolMessage）

运行：.venv\\Scripts\\python scripts/smoke_m15_state.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402

from app import sessions, store  # noqa: E402

PASS = 0
FAIL = 0
MEMBER = 7001


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
    """每条 ToolMessage 前面必须紧跟一个带同名 tool_call_id 的 AIMessage。"""
    for i, m in enumerate(msgs):
        if type(m).__name__ != "ToolMessage":
            continue
        prev = msgs[i - 1] if i else None
        if not getattr(prev, "tool_calls", None):
            return False
        if prev.tool_calls[0].get("id") != m.tool_call_id:
            return False
    return True


# ---------------------------------------------------------------- 造数据

PIC = "http://oss.example.com/" + "x" * 400      # 长 URL 是 token 大头，正是要省掉的


def search_round(i: int, items: int = 3):
    """一轮"搜索"：提问 → 调 search_products → 大 JSON 结果 → 回答。"""
    data = [{"id": 100 + i * 10 + k, "name": f"降噪耳机{i}-{k}", "price": 199 + k,
             "pic": PIC, "productSn": f"SN{i}{k}", "sale": 88, "status": 1}
            for k in range(items)]
    return [
        HumanMessage(content=f"第{i}轮：帮我找降噪耳机"),
        AIMessage(content="", tool_calls=[{"name": "search_products",
                                          "args": {"keyword": "降噪耳机"}, "id": f"c{i}"}]),
        ToolMessage(content=json.dumps(data, ensure_ascii=False),
                    tool_call_id=f"c{i}", name="search_products"),
        AIMessage(content=f"第{i}轮：为你找到 {items} 款"),
    ]


def preview_round(i: int):
    """一轮"生成确认单"（草稿未消费）。"""
    body = {"cartPromotionItemList": [{"productName": f"耳机{i}", "price": 199, "quantity": 1}],
            "memberReceiveAddressList": [{"id": 1, "name": "张三"}],
            "calcAmount": {"totalAmount": 199, "payAmount": 199}}
    return [
        HumanMessage(content=f"第{i}轮：帮我下单"),
        AIMessage(content="", tool_calls=[{"name": "preview_order", "args": {"cart_id": 5}, "id": f"p{i}"}]),
        ToolMessage(content=json.dumps(body, ensure_ascii=False),
                    tool_call_id=f"p{i}", name="preview_order"),
        AIMessage(content=f"第{i}轮：请核对订单，点击确认下单"),
    ]


def place_round(i: int):
    """一轮"已下单"。"""
    return [
        HumanMessage(content="【系统指令】用户已确认下单，draft_id=abc"),
        AIMessage(content="", tool_calls=[{"name": "place_order", "args": {"draft_id": "abc"}, "id": f"o{i}"}]),
        ToolMessage(content=json.dumps({"id": 900 + i, "orderSn": f"SN{i}", "payAmount": 199},
                                       ensure_ascii=False),
                    tool_call_id=f"o{i}", name="place_order"),
        AIMessage(content=f"第{i}轮：下单成功，订单号 SN{i}"),
    ]


def plain_round(i: int):
    return [HumanMessage(content=f"第{i}轮：随便聊聊"),
            AIMessage(content=f"第{i}轮：好的")]


# ---------------------------------------------------------------- Part A

def part_a_storage():
    print("\n===== Part A：存储层（迁移 + 只增不减）=====")
    sid = "m15test-store"
    store.clear_session(sid)

    # A1 存量数据是 String(JSON 数组) —— 模拟 M1 期间写下的旧格式
    legacy = sessions._to_dicts([HumanMessage(content="我叫小明"), AIMessage(content="你好，小明")])
    store.client().set(store._k_messages(sid), json.dumps(legacy, ensure_ascii=False))
    store.client().hset(store._k_meta(sid), mapping={"memberId": str(MEMBER)})
    check("A1 迁移前键类型为 string", store.client().type(store._k_messages(sid)) == "string")

    got = sessions.get_history(sid, MEMBER)
    check("A2 旧数据可透明读回（迁移为 List）",
          len(got) == 2 and got[0].content == "我叫小明"
          and store.client().type(store._k_messages(sid)) == "list",
          f"读回 {len(got)} 条 / type={store.client().type(store._k_messages(sid))}")

    got2 = sessions.get_history(sid, MEMBER)
    check("A3 迁移幂等（再读一次结果一致）", len(got2) == 2)

    # A4 追加写：条数累加、顺序正确
    before = store.count_messages(sid)
    sessions.append_turn(sid, [HumanMessage(content="第二句"), AIMessage(content="收到")], MEMBER)
    after = store.count_messages(sid)
    tail = sessions.get_history(sid, MEMBER)[-2:]
    check("A4 追加写：条数累加且顺序正确",
          after == before + 2 and tail[0].content == "第二句",
          f"{before} -> {after}")

    # A5 装配是只读的：压缩视图不写回事实源
    big = [m for i in range(8) for m in search_round(i)]
    sessions.reset_history(sid, big, MEMBER)
    n0 = store.count_messages(sid)
    keep_budget, keep_hot = sessions.TOKEN_BUDGET, sessions.HOT_ROUNDS
    sessions.TOKEN_BUDGET, sessions.HOT_ROUNDS = 1200, 2
    view, _n = sessions.assemble_history(sid, MEMBER, [HumanMessage(content="再来")])
    sessions.TOKEN_BUDGET, sessions.HOT_ROUNDS = keep_budget, keep_hot
    n1 = store.count_messages(sid)
    check("A5 装配只读：事实源条数不变（压缩视图不入库）",
          n1 == n0 and len(view) < n0, f"存储 {n0} 条不变，装配视图 {len(view)} 条")

    store.clear_session(sid)


# ---------------------------------------------------------------- Part B

def part_b_assembly():
    print("\n===== Part B：分级降级装配 =====")
    sid = "m15test-assemble"
    store.clear_session(sid)
    keep_budget, keep_hot, keep_head = sessions.TOKEN_BUDGET, sessions.HOT_ROUNDS, sessions.HEAD_KEEP_ROUNDS
    try:
        big = [m for i in range(10) for m in search_round(i)]
        sessions.HOT_ROUNDS, sessions.HEAD_KEEP_ROUNDS = 2, 2

        t0 = sessions._est_tokens(big)
        stub = sessions.stub_tools(big)
        t1 = sessions._est_tokens(stub)
        fold = sessions.fold_middle(stub)
        t2 = sessions._est_tokens(fold)
        print(f"  （估算 token：原样 {t0} → 桩化 {t1} → 折叠 {t2}）")

        # B1 T0 原样
        sessions.TOKEN_BUDGET = t0 + 100
        _, lv = sessions._assemble(sid, big, [])
        check("B1 不超预算 → T0 原样", lv == "T0", f"level={lv}")

        # B2 T1 标记化
        sessions.TOKEN_BUDGET = t1
        view1, lv = sessions._assemble(sid, big, [])
        stubs = [m for m in view1 if type(m).__name__ == "ToolMessage"
                 and isinstance(m.content, str) and '"_stub"' in m.content]
        hot_tools = [m for m in view1 if type(m).__name__ == "ToolMessage"
                     and isinstance(m.content, str) and "pic" in m.content]
        ok_json = False
        if stubs:
            d = json.loads(stubs[0].content)
            first = (d.get("items") or [{}])[0]
            ok_json = all(k in first for k in ("id", "name", "price"))
        check("B2 T1 桩化：冷区工具消息瘦身、热区保原文、桩保留 id/名称/价格",
              lv == "T1" and len(stubs) > 0 and len(hot_tools) == 2 and ok_json and paired(view1)
              and t1 < t0,
              f"level={lv} 桩 {len(stubs)} 条 / 热区原文 {len(hot_tools)} 条 / {t0}→{t1} token")

        # B3 T2 中间轮折叠
        sessions.TOKEN_BUDGET = t2
        view2, lv = sessions._assemble(sid, big, [])
        texts = [m.content for m in view2 if isinstance(getattr(m, "content", None), str)]
        has_placeholder = any("【历史折叠】" in t for t in texts)
        human = [m.content for m in view2 if type(m).__name__ == "HumanMessage"]
        check("B3 T2 折叠：保头部 + 最近轮，中间换成占位、配对完整",
              lv == "T2" and has_placeholder
              and any("第0轮" in h for h in human) and any("第9轮" in h for h in human)
              and not any("第4轮" in h for h in human)
              and paired(view2) and t2 < t1,
              f"level={lv} 保留 {len(human)} 轮 / {t1}→{t2} token")

        # B4 草稿钉住：中间轮含未消费 preview_order → 不折叠
        mixed = (plain_round(0) + plain_round(1) + preview_round(2) + plain_round(3)
                 + plain_round(4) + plain_round(5))
        pinned = sessions.fold_middle(mixed)
        pinned_human = [m.content for m in pinned if type(m).__name__ == "HumanMessage"]
        check("B4 含未消费草稿的轮次被钉住（不被折叠）",
              any("帮我下单" in h for h in pinned_human) and paired(pinned),
              f"折叠后保留 {len(pinned_human)} 轮")

        # B4' 对照组：草稿已被 place_order 消费 → 该轮可被折叠
        mixed2 = ([m for i in range(2) for m in plain_round(i)]
                  + preview_round(2)
                  + [m for i in range(3, 6) for m in place_round(i)])
        unpinned = sessions.fold_middle(mixed2)
        unpinned_human = [m.content for m in unpinned if type(m).__name__ == "HumanMessage"]
        check("B5 草稿已被下单消费的轮次 → 允许折叠（对照组）",
              not any("帮我下单" in h for h in unpinned_human) and paired(unpinned),
              f"折叠后保留 {len(unpinned_human)} 轮")

        # B6 装配诊断可观测（预算 = 折叠后 + 余量，预留本轮消息的 token）
        sessions.TOKEN_BUDGET = t2 + 50
        sessions.reset_history(sid, big, MEMBER)
        sessions.assemble_history(sid, MEMBER, [HumanMessage(content="hi")])
        info = store.load_assembly(sid)
        check("B6 装配级别写入诊断键（可观测）",
              info.get("level") == "T2" and info.get("stored") == len(big),
              json.dumps(info, ensure_ascii=False))

        # B7 预算极小时不崩（软约束）
        sessions.TOKEN_BUDGET = 1
        view3, lv = sessions._assemble(sid, big, [])
        check("B7 预算极小也不抛错（软约束：宁可略超也不挂）",
              lv == "T3" and paired(view3), f"level={lv} 视图 {len(view3)} 条")
    finally:
        sessions.TOKEN_BUDGET, sessions.HOT_ROUNDS, sessions.HEAD_KEEP_ROUNDS = keep_budget, keep_hot, keep_head
        store.clear_session(sid)


if __name__ == "__main__":
    store.assert_available()
    print(f"Redis: {store._mask(store.config.REDIS_URL)}")
    part_a_storage()
    part_b_assembly()
    print(f"\n===== 结果：{PASS} 通过 / {FAIL} 失败 =====")
    sys.exit(1 if FAIL else 0)
