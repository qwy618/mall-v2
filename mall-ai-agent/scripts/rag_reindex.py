"""重建 RAG 索引的 CLI。

用法：
    python scripts/rag_reindex.py --check            # 只读：Qdrant/元数据/一致性/定时调度现状
    python scripts/rag_reindex.py --full             # 全量构建（幂等 upsert + 陈旧清理）
    python scripts/rag_reindex.py --full --force     # 重建 collection（换模型/维度、或索引损坏）
    python scripts/rag_reindex.py --product 40       # 只刷单个商品
    python scripts/rag_reindex.py --search "屏幕 续航 体验"   # 检索自测

设计取舍：**不用 `--workers`、不并发**。当前规模（~38 商品）单进程几十秒；
并发会让 LLM 聚合触发限流，且日志难读。规模上千时再改分片批处理（docs §11 债务）。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config, store                     # noqa: E402
from app.rag import indexer, retriever, vector_store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rag_reindex")


def show_check() -> int:
    sh = vector_store.health()
    print("=== Qdrant ===")
    print(json.dumps(sh, ensure_ascii=False, indent=2))

    print("\n=== Redis 索引元数据（ai:rag:meta）===")
    try:
        meta = store.load_rag_meta()
        print(json.dumps(meta, ensure_ascii=False, indent=2) if meta else "（空 → 尚未建过索引）")
        print(f"锁持有中: {store.peek_rag_lock()}")
    except Exception as e:  # noqa: BLE001
        print(f"读取失败：{e}")

    # 结论式诊断：把"实况 vs 元数据"对账成一句话 —— 退出码即"要不要重建"
    print("\n=== 索引一致性（需不需要重建）===")
    st = indexer.index_status()
    print(json.dumps({k: v for k, v in st.items() if k != "meta"},
                     ensure_ascii=False, indent=2))

    # 调度器按需导入：这是纯只读诊断，不该因 scheduler/apscheduler 出问题而整体失败
    print("\n=== 定时调度（M3.3）===")
    try:
        from app import scheduler
        print(json.dumps(scheduler.status(), ensure_ascii=False, indent=2))
    except Exception as e:  # noqa: BLE001
        print(f"调度器不可用：{e}")

    print("\n=== 配置 ===")
    print(json.dumps({
        "RAG_ENABLED": config.RAG_ENABLED,
        "QDRANT_URL": config.QDRANT_URL,
        "collection": config.RAG_COLLECTION,
        "EMBED_MODEL": config.EMBED_MODEL,
        "EMBED_DIM": config.EMBED_DIM,
        "RAG_TOP_K": config.RAG_TOP_K,
        "RAG_SIM_THRESHOLD": config.RAG_SIM_THRESHOLD,
        "RAG_MIN_REVIEWS": config.RAG_MIN_REVIEWS,
        "RAG_INDEX_CRON": config.RAG_INDEX_CRON,
        "RAG_INDEX_ON_START": config.RAG_INDEX_ON_START,
    }, ensure_ascii=False, indent=2))

    if not st.get("ok"):
        print("\n提示：索引需要重建（原因见上）→ 跑 `--full`"
              + ("（含维度变更，加 `--force`）" if st.get("needForce") else ""))
    return 0 if st.get("ok") else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="RAG 索引构建与自测")
    ap.add_argument("--check", action="store_true", help="只读：打印 Qdrant / 元数据 / 配置现状")
    ap.add_argument("--full", action="store_true", help="全量构建")
    ap.add_argument("--force", action="store_true", help="重建 collection（维度变更/损坏时）")
    ap.add_argument("--product", type=int, default=None, help="只刷单个商品 id")
    ap.add_argument("--no-reviews", action="store_true", help="只建商品档案，跳过评价聚合（省 LLM 调用）")
    ap.add_argument("--search", type=str, default=None, help="检索自测（不需要先建索引）")
    ap.add_argument("--top-k", type=int, default=None, help="检索自测的 topK")
    args = ap.parse_args()

    if args.check:
        return show_check()

    if args.search is not None:
        res = retriever.search_knowledge_impl(args.search, top_k=args.top_k)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("hit") else 2

    if args.product is not None:
        res = indexer.build_with_lock(only_product=args.product)
    elif args.full:
        res = indexer.build_with_lock(force=args.force)
    else:
        ap.print_help()
        return 1

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
