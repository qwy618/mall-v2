"""M3.2 验收：知识检索工具 + 路由分道 + 反幻觉红线。

分两段：
  A. **工具层直连**（不依赖 LLM）：`search_knowledge.invoke()` 能否命中/拒答/过滤。
     这段是分诊器 —— 挂了说明"工具接错后端"，不是"LLM 用错工具"。
  B. **LLM 路由 E2E**：语义类问题必须走 search_knowledge；
     价格类问题**必须不走** search_knowledge（价格只认工具实时值）。

可重复运行：使用独立 session，跑前清空。

用法：./.venv/Scripts/python.exe scripts/smoke_m3_agent.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage          # noqa: E402

from app import config, store                             # noqa: E402
from app.agent import build_agent                         # noqa: E402
from app.tools.knowledge_tools import search_knowledge    # noqa: E402

SESSION = "smoke-m3-agent"
ok = fail = 0


def check(label: str, cond: bool, extra: str = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {label}" + (f"  {extra}" if extra else ""))
    else:
        fail += 1
        print(f"  [FAIL] {label}" + (f"  {extra}" if extra else ""))


def call_tool(**kwargs) -> dict:
    """直连工具（不经 LLM）。langchain @tool 用 .invoke 传 dict。"""
    raw = search_knowledge.invoke(kwargs)
    return json.loads(raw)


def tool_names(msgs) -> list[str]:
    out = []
    for m in msgs:
        for tc in (getattr(m, "tool_calls", None) or []):
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if name:
                out.append(name)
    return out


def run(agent, history, text):
    print(f"\n[用户] {text}")
    before = len(history)
    result = agent.invoke({"messages": history + [HumanMessage(content=text)]})
    msgs = result["messages"]
    for m in msgs[before:]:
        for tc in (getattr(m, "tool_calls", None) or []):
            print(f"  -> {tc.get('name')}({tc.get('args')})")
    print(f"[小M] {getattr(msgs[-1], 'content', '')}")
    return msgs


def main() -> int:
    print(f"collection={config.RAG_COLLECTION} threshold={config.RAG_SIM_THRESHOLD}")

    # ---------------- A. 工具层直连 ----------------
    print("\n=== A. 工具层直连（不依赖 LLM）===")
    hit = call_tool(query="手机 屏幕 续航 发热 用起来怎么样")
    check("语义 query hit=true", bool(hit.get("hit")), json.dumps(hit, ensure_ascii=False)[:120])
    check("items 非空", len(hit.get("items") or []) > 0)
    if hit.get("items"):
        it = hit["items"][0]
        check("item 只含可展示字段（无 score/indexedAt）",
              not ({"score", "indexedAt", "categoryId"} & set(it)),
              str(sorted(it.keys())))

    miss = call_tool(query="红烧肉怎么做 家常菜谱")
    check("无关 query hit=false", not miss.get("hit"), json.dumps(miss, ensure_ascii=False))
    check("拒答时 items 为空", not (miss.get("items") or []))

    bad_pid = call_tool(query="体验 口碑", product_ids="not-a-json")
    check("非法 product_ids 不炸（当没传处理）", isinstance(bad_pid, dict))

    ids = [it["productId"] for it in (hit.get("items") or [])][:2]
    if ids:
        r = call_tool(query="体验 口碑", product_ids=json.dumps(ids))
        got = {it["productId"] for it in (r.get("items") or [])}
        check("product_ids 过滤生效", got.issubset(set(ids)), f"got={sorted(got)}")

    # ---------------- B. LLM 路由 E2E ----------------
    print("\n=== B. LLM 路由 E2E ===")
    try:
        store.client().delete(f"ai:session:{SESSION}:messages")
        store.client().delete(f"ai:session:{SESSION}:meta")
    except Exception as e:  # noqa: BLE001
        print(f"  (清理会话失败，忽略：{e})")

    agent = build_agent()
    history = []

    history = run(agent, history, "我想了解一下小米12 Pro 这款手机用起来怎么样，口碑如何？槽点多吗？")
    names = tool_names(history)
    check("语义类问题走了 search_knowledge", "search_knowledge" in names, f"工具序列={names}")
    answer = str(getattr(history[-1], "content", "") or "")
    check("回答提到了具体商品名", "小米" in answer or "12" in answer, answer[:60])

    before_len = len(history)
    history = run(agent, history, "那小米12 Pro 现在多少钱？")
    names2 = tool_names(history[before_len:])
    check("价格类问题**未**调用 search_knowledge",
          "search_knowledge" not in names2, f"工具序列={names2}")
    check("价格类问题调用了实时工具",
          any(n in ("get_product_detail", "search_products") for n in names2),
          f"工具序列={names2}")

    print(f"\n{'=' * 46}\n结果：{ok} 通过 / {fail} 失败\n{'=' * 46}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
