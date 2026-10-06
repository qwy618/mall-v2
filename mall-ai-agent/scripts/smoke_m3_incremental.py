"""M3.3 验收：定时增量索引（cron / 单飞锁 / 指纹自愈 / 启动自检）。

可重复运行、**不重建真实索引**（不写真实 collection、除单飞锁外不改 Redis、不改 .env），
只验证"调度链路"与"自愈判定"；真实重建由 `scripts/rag_reindex.py --full` 负责。

覆盖（对应 docs §9.1 的 M3.3 三条验收 + 启动自检）：
  A. cron 与调度器：表达式可解析、下次触发时间正确、APScheduler 在本环境真能触发、startup/shutdown 幂等
  B. 任务链路：`_job()` 走 `build_with_lock`；构建期间持锁、事后释放；构建异常被吞不外抛
  C. 单飞锁（**多 worker 只跑一次**的核心）：锁被他人持有 → `skipped` 且不触发构建；
     token 不符不能误释放别人的锁
  D. 指纹自愈：`index_status()` 能识别"维度/模型变更"；`ensure_collection` 维度不符自动重建
  E. 启动自检：索引一致 → 不构建；索引失效 → 构建一次且带 `force`

用法：
    ./.venv/Scripts/python.exe scripts/smoke_m3_incremental.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config, scheduler, store          # noqa: E402
from app.rag import indexer, vector_store         # noqa: E402

PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def _fake_build(log_list: list, result: dict | None = None):
    """替身 build：记录调用参数与"调用瞬间锁是否被持有"，不真跑索引。"""
    def _f(force: bool = False, only_product=None, with_reviews: bool = True) -> dict:
        log_list.append({"force": force, "onlyProduct": only_product,
                         "lockHeld": store.peek_rag_lock()})
        return result or {"ok": True, "docs": 0, "removedStale": 0,
                          "errors": 0, "elapsed": 0.0, "meta": {}}
    return _f


# ---------------------------------------------------------------- A. cron 与调度器
def test_a() -> None:
    section("A. cron 与调度器")
    print(f"  cron={config.RAG_INDEX_CRON}  onStart={config.RAG_INDEX_ON_START}")

    try:
        from apscheduler.triggers.cron import CronTrigger
        trig = CronTrigger.from_crontab(config.RAG_INDEX_CRON)
        now = datetime.now()
        nxt = trig.get_next_fire_time(None, now)
        check("cron 表达式可解析", nxt is not None, f"下次触发 {nxt}")
        # 五段 cron 是「分 时 日 月 周」——前两个字段依次是 分、时
        minute, hour = (int(x) for x in config.RAG_INDEX_CRON.split()[:2])
        check("下次触发时间与 cron 的时/分一致",
              nxt is not None and nxt.hour == hour and nxt.minute == minute,
              f"期望 {hour:02d}:{minute:02d}，实际 {nxt}")
        # 触发器返回带时区时间，比较基准也要带时区（本机 UTC+8）
        now_aware = datetime.now(nxt.tzinfo) if (nxt is not None and nxt.tzinfo) else now
        check("下次触发在 24h 内",
              nxt is not None and now_aware < nxt <= now_aware + timedelta(days=1))
    except ImportError:  # pragma: no cover
        check("apscheduler 已安装", False, "pip install apscheduler")

    # ⚠️ AsyncIOScheduler.start() 只能跑在**运行中的事件循环**里（这正是它挂在 FastAPI
    # lifespan 下的原因）→ 同步脚本里必须先包进 asyncio.run，否则 RuntimeError。
    # 同时强制关掉"启动即建索引"，避免测试真的触发一次全量重建。
    orig_on_start = config.RAG_INDEX_ON_START
    config.RAG_INDEX_ON_START = False

    async def _async_probe() -> tuple[dict, dict, int]:
        # 1) 生命周期：startup() 注册任务 → status → shutdown（且可重复调用）
        scheduler.startup()
        st_live = scheduler.status()
        scheduler.shutdown()
        st_stopped = scheduler.status()
        scheduler.shutdown()            # 幂等：--reload 下 lifespan 会反复进入
        # 2) 真跑一个 APScheduler：确认本环境（asyncio + 同步 job）确实能到点触发
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        hits: list[int] = []
        s = AsyncIOScheduler()
        s.add_job(lambda: hits.append(1), IntervalTrigger(seconds=1), id="probe")
        s.start()
        await asyncio.sleep(2.6)
        s.shutdown(wait=False)
        return st_live, st_stopped, len(hits)

    try:
        st, st_after, n = asyncio.run(_async_probe())
    finally:
        config.RAG_INDEX_ON_START = orig_on_start

    check("startup() 后调度器在跑且已排下次触发",
          bool(st.get("running")) and bool(st.get("nextRunTime")),
          f"nextRunTime={st.get('nextRunTime')}")
    check("status() 字段完备",
          all(k in st for k in ("enabled", "cron", "onStart", "hasApscheduler",
                                "running", "jobId")),
          json.dumps(st, ensure_ascii=False))
    check("shutdown() 后调度器已停止", st_after.get("running") is False)
    check("shutdown() 可重复调用（幂等）", True)
    check("APScheduler 在 asyncio 环境下真能到点触发", n >= 2, f"2.6s 内触发 {n} 次")


# ---------------------------------------------------------------- B. 任务链路
def test_b() -> None:
    section("B. _job() 任务链路")
    orig_build = indexer.build
    calls: list = []
    indexer.build = _fake_build(calls)
    try:
        scheduler._job()
    finally:
        indexer.build = orig_build
    check("_job() 经 build_with_lock 触发了一次构建", len(calls) == 1)
    check("构建期间持有 ai:rag:lock", bool(calls and calls[0]["lockHeld"]))
    check("构建结束后锁已释放", not store.peek_rag_lock())
    check("全量构建（未指定单商品）", bool(calls) and calls[0]["onlyProduct"] is None)

    def _boom(*_a, **_k):
        raise RuntimeError("smoke-boom")

    indexer.build = _boom
    try:
        scheduler._job()
        ok = True
    except Exception:  # noqa: BLE001
        ok = False
    finally:
        indexer.build = orig_build
    check("构建抛异常被吞（不拖垮对话服务）", ok)
    check("异常后锁也被释放（finally 生效）", not store.peek_rag_lock())


# ---------------------------------------------------------------- C. 单飞锁
def test_c() -> None:
    section("C. 单飞锁（多 worker 只跑一次）")
    token = "smoke-hold-" + uuid.uuid4().hex

    check("能抢到 ai:rag:lock", store.acquire_rag_lock(token, ttl=60))
    calls: list = []
    orig_build = indexer.build
    indexer.build = _fake_build(calls)
    try:
        res = indexer.build_with_lock()
    finally:
        indexer.build = orig_build

    check("锁被他人持有时返回 skipped（不是错误）", res.get("skipped") is True,
          str(res.get("reason", "")))
    check("skipped 时一次构建都没触发", len(calls) == 0)
    check("skipped 时不影响别人的锁", store.peek_rag_lock())

    store.release_rag_lock("wrong-token-" + uuid.uuid4().hex)
    check("token 不符 → 不能误释放别人的锁（Lua 校验）", store.peek_rag_lock())

    store.release_rag_lock(token)
    check("正确 token → 释放成功", not store.peek_rag_lock())

    calls2: list = []
    indexer.build = _fake_build(calls2)
    try:
        res2 = indexer.build_with_lock()
    finally:
        indexer.build = orig_build
    check("锁空闲时 build_with_lock 正常执行", not res2.get("skipped") and len(calls2) == 1)
    check("正常路径执行后锁已释放", not store.peek_rag_lock())


# ---------------------------------------------------------------- D. 指纹自愈
def test_d() -> None:
    section("D. 指纹与自愈（真实库只读判定）")
    st = indexer.index_status()
    check("真实索引自检通过（无需重建）", bool(st.get("ok")),
          "；".join(st.get("reasons") or []) or f"points={st.get('points')} dim={st.get('dim')}")
    check("自检含 needForce / reasons 字段",
          "needForce" in st and "reasons" in st)

    orig_dim = config.EMBED_DIM
    try:
        config.EMBED_DIM = orig_dim + 1024
        st2 = indexer.index_status()
        check("EMBED_DIM 变更 → 判定索引失效", not st2.get("ok"))
        check("失效原因指向维度", any("维度" in r for r in (st2.get("reasons") or [])),
              "；".join(st2.get("reasons") or []))
        check("维度类问题要求 force 重建", bool(st2.get("needForce")))
    finally:
        config.EMBED_DIM = orig_dim

    # 用**临时 collection** 验证"维度不符 → ensure_collection 自动重建"（不碰真实索引）
    orig_coll = config.RAG_COLLECTION
    tmp = "mall_knowledge_smoke_tmp"
    d1 = d2 = None
    try:
        config.RAG_COLLECTION = tmp
        config.EMBED_DIM = 64
        vector_store.ensure_collection()
        d1 = vector_store.collection_dim()
        config.EMBED_DIM = 128
        vector_store.ensure_collection()     # 维度不符 → 应自动 delete + recreate
        d2 = vector_store.collection_dim()
    finally:
        try:
            vector_store.client().delete_collection(tmp)
        except Exception:  # noqa: BLE001
            pass
        config.RAG_COLLECTION = orig_coll
        config.EMBED_DIM = orig_dim

    check("临时 collection 按 64 维创建", d1 == 64, f"dim={d1}")
    check("EMBED_DIM 改 128 → 自动重建为 128 维", d2 == 128, f"dim={d2}")
    check("临时 collection 已清理", vector_store.collection_dim(tmp) is None)
    check("真实 collection 未受影响",
          vector_store.collection_dim(orig_coll) == orig_dim,
          f"dim={vector_store.collection_dim(orig_coll)}")


# ---------------------------------------------------------------- E. 启动自检
def test_e() -> None:
    section("E. 启动自检（RAG_INDEX_ON_START 语义）")
    orig_build, orig_status = indexer.build, indexer.index_status

    calls: list = []
    indexer.build = _fake_build(calls)
    indexer.index_status = lambda: {"ok": True, "points": 40, "dim": config.EMBED_DIM,
                                    "reasons": [], "needForce": False}
    try:
        scheduler._bootstrap_build()
        check("索引一致 → 启动不构建", len(calls) == 0)
    finally:
        pass

    indexer.index_status = lambda: {"ok": False, "points": 0, "dim": None,
                                    "reasons": ["维度不符（库内 512 != EMBED_DIM 1024）"],
                                    "needForce": True}
    try:
        scheduler._bootstrap_build()
    finally:
        indexer.build, indexer.index_status = orig_build, orig_status

    check("索引失效 → 启动构建一次", len(calls) == 1)
    check("维度类失效 → 构建带 force=True", bool(calls) and calls[0]["force"] is True)
    check("自检后不残留锁", not store.peek_rag_lock())

    st = indexer.index_status()
    check("还原后真实索引自检仍通过", bool(st.get("ok")),
          "；".join(st.get("reasons") or []))


def main() -> int:
    print(f"M3.3 验收 · Qdrant={config.QDRANT_URL} collection={config.RAG_COLLECTION}")
    print("（只读：不重建真实索引；仅操作 ai:rag:lock 与临时 collection）")
    test_a()
    test_b()
    test_c()
    test_d()
    test_e()
    print(f"\n===== 结果：{PASS} 通过 / {FAIL} 失败 =====")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
