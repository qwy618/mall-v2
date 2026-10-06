"""M3.1 验收：索引质量 + 检索闸门 + **价格红线**。

可重复运行、只读（不写 Qdrant/Redis，不产生副作用），失败即非零退出。

覆盖：
  A. 集合指纹：collection 存在、维度 == EMBED_DIM、文档数与 meta 一致
  B. 文档结构：两类文档齐备、payload 必需字段完备、脏数据未入库
  C. 🔴 价格红线：全部 payload + text 中**零金额**（快照入向量库 = 幻觉源）
  D. 检索命中：语义 query 命中正确商品且 maxScore ≥ 阈值
  E. L1 拒答：无关 query 必须 hit=false / reason=below_threshold
  F. 过滤：product_ids（两段式）与 category_id 预过滤生效

用法：
    python -m scripts.smoke_m3_rag          # 或
    ./.venv/Scripts/python.exe scripts/smoke_m3_rag.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config, store                     # noqa: E402
from app.rag import retriever, vector_store       # noqa: E402

PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))


# 金额表达式（与 app/rag/aggregate.py 的出口清洗同款）
_AMOUNT_RE = re.compile(
    r"(?:¥|￥|\$)\s*\d+(?:\.\d{1,2})?"
    r"|\d+(?:\.\d{1,2})?\s*(?:元|块钱|块|人民币)"
)
# 星数/条数形如 "4.2 分"「6 条」不算金额，故上面只匹配带货币符号或"元/块"的


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    print(f"Qdrant={config.QDRANT_URL} collection={config.RAG_COLLECTION} "
          f"dims={config.EMBED_DIM} threshold={config.RAG_SIM_THRESHOLD}")

    # ---------------- A. 集合指纹 ----------------
    section("A. 集合指纹")
    sh = vector_store.health()
    check("Qdrant 可达", bool(sh.get("ok")), str(sh.get("error", "")))
    check("collection 已创建", bool(sh.get("exists")))
    check("维度一致", bool(sh.get("consistent")), f"dim={sh.get('dim')}")
    points = sh.get("points") or 0
    check("文档数 > 0", points > 0, f"points={points}")

    meta = store.load_rag_meta() if sh.get("ok") else {}
    if meta:
        check("meta.docCount 与实况一致", int(meta.get("docCount", -1)) == points,
              f"meta={meta.get('docCount')} actual={points}")
        check("meta 指纹（模型/维度）一致",
              meta.get("embedModel") == config.EMBED_MODEL
              and int(meta.get("embedDim", 0)) == config.EMBED_DIM)
    else:
        check("索引元数据存在", False, "ai:rag:meta 为空")

    # ---------------- B. 文档结构 ----------------
    section("B. 文档结构")
    allp = vector_store.scroll_all()
    profiles = [p for p in allp if p["payload"].get("docType") == "product_profile"]
    summaries = [p for p in allp if p["payload"].get("docType") == "review_summary"]
    check("存在 product_profile 文档", len(profiles) > 0, f"{len(profiles)} 条")
    check("存在 review_summary 文档", len(summaries) > 0, f"{len(summaries)} 条")
    check("文档类型只有这两类",
          len(profiles) + len(summaries) == len(allp), f"{len(allp)} 条总计")

    req = ("docType", "productId", "name", "categoryId", "indexedAt")
    missing = [(p["payload"].get("productId"), k) for p in allp
               for k in req if k not in p["payload"]]
    check("payload 必需字段完备", not missing, str(missing[:3]))

    dirty = [p for p in allp
             if re.match(config.RAG_SKIP_NAME_PATTERN, (p["payload"].get("name") or "").strip(), re.I)]
    check("脏数据商品未入库", not dirty, str([p["payload"].get("name") for p in dirty][:3]))

    # ---------------- C. 🔴 价格红线 ----------------
    section("C. 价格/库存红线（最高优先级）")
    bad_fields = []
    for p in allp:
        for k in p["payload"]:
            if k in ("price", "lowestPrice", "stock", "lockStock", "pic", "pics", "productSn"):
                bad_fields.append((p["payload"].get("productId"), k))
    check("payload 无价格/库存/图片/序列号字段", not bad_fields, str(bad_fields[:3]))

    amount_hits = []
    for p in allp:
        pj = json.dumps(p["payload"], ensure_ascii=False)
        for m in _AMOUNT_RE.findall(pj):
            amount_hits.append((p["payload"].get("productId"), m))
    check("payload 全文无金额表达式", not amount_hits, str(amount_hits[:5]))

    # ---------------- D. 检索命中 ----------------
    section("D. 语义检索命中")
    hit = retriever.search_knowledge_impl("这个手机用起来怎么样 屏幕 续航 发热")
    check("相关 query 命中", bool(hit.get("hit")), json.dumps(hit.get("reason")))
    check("maxScore ≥ 阈值", hit.get("maxScore", 0) >= config.RAG_SIM_THRESHOLD,
          f"{hit.get('maxScore')} vs {config.RAG_SIM_THRESHOLD}")
    check("返回非空 items", len(hit.get("items") or []) > 0)
    if hit.get("items"):
        it = hit["items"][0]
        check("item 含必要字段",
              all(k in it for k in ("productId", "name", "docType", "snippet", "score")))
        check("snippet 内无金额", not _AMOUNT_RE.search(it.get("snippet", "")),
              it.get("snippet", "")[:80])

    # ---------------- E. L1 拒答 ----------------
    section("E. L1 拒答闸门")
    miss = retriever.search_knowledge_impl("如何做红烧肉 菜谱 步骤")
    check("无关 query 不命中", not miss.get("hit"), json.dumps(miss.get("reason")))
    check("拒答原因为低于阈值",
          miss.get("reason") == "below_threshold", str(miss.get("reason")))
    check("拒答时不返回 item 列表给用户用",
          miss.get("maxScore", 1) < config.RAG_SIM_THRESHOLD)

    # ---------------- F. 过滤 ----------------
    section("F. 预过滤（两段式 / 分类）")
    target_ids = [it["productId"] for it in (hit.get("items") or [])][:3]
    if target_ids:
        res = retriever.search_knowledge_impl("体验 口碑", product_ids=target_ids)
        got = {it["productId"] for it in (res.get("items") or [])}
        check("product_ids 过滤生效", got.issubset(set(target_ids)),
              f"got={sorted(got)} allowed={sorted(target_ids)}")

    # 同一 query 限定到"该商品所在分类"应仍能命中
    if hit.get("items"):
        pid = hit["items"][0]["productId"]
        prof = next((p for p in profiles if p["payload"].get("productId") == pid), None)
        cid = (prof or {}).get("payload", {}).get("categoryId")
        if cid:
            res2 = retriever.search_knowledge_impl("用起来怎么样", category_id=cid)
            check("category_id 过滤生效（同分类可命中）", bool(res2.get("hit")),
                  f"categoryId={cid} maxScore={res2.get('maxScore')}")
            res3 = retriever.search_knowledge_impl("用起来怎么样", category_id=999999)
            check("category_id 无匹配时拒答", not res3.get("hit"), str(res3.get("reason")))

    # ---------------- 汇总 ----------------
    print(f"\n{'=' * 46}\n结果：{PASS} 通过 / {FAIL} 失败\n{'=' * 46}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
