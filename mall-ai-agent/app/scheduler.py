"""M3.3 定时增量索引（APScheduler）。

**为什么是"定时全量"而不是 MQ 增量**（docs `M3_RAG检索增强设计.md` §5.3）：
mall 的商品同步监听器在 **Java 进程内**消费 RabbitMQ 同步 ES，agent 想接同一队列
就得改 Java 侧（违反"助手只经 REST、不动 Java"的边界），而语义内容（评价）是**低频写**，
定时全量在当前规模（~40 文档 / 几十秒）成本极低 → 直接用调度器。

**多 worker 事实**（M1 起就定下的铁律）：`uvicorn --workers N` 会 fork N 个**独立进程**，
每个进程都会挂一个 scheduler、在同一时刻到点触发 → 靠 **`ai:rag:lock` 单飞**，
只有抢到锁的进程真正重建，其余 `skipped=True`（**这不是错误**，只是"别人在干"）。

**三种触发**（互为补充，不冲突）：
  1. 定时：`RAG_INDEX_CRON`（默认 `0 3 * * *` 低峰）
  2. 启动自检：`RAG_INDEX_ON_START=1` 且 `index_status()` 判定索引失效/缺失 → 后台线程建一次
  3. 手动：`python scripts/rag_reindex.py --full`
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

try:  # 缺包也不该拖垮服务：没装就退化为"手动/外部 cron"
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    _HAS_APS = True
except ImportError:  # pragma: no cover
    _HAS_APS = False

from . import config, store  # noqa: F401  (store 供验收脚本/诊断复用)
from .rag import indexer

log = logging.getLogger(__name__)

JOB_ID = "rag_reindex"

_scheduler = None


# ---------------------------------------------------------------- 任务体

def _job() -> None:
    """定时任务体：全量重建（带单飞锁）。

    ⚠️ 任何异常都必须吞掉并记日志——索引坏了不能让**整个对话服务**跟着挂。
    降级路径是现成的：检索不到就 `hit=false` → 走拒答话术，其余工具照常。
    """
    try:
        res = indexer.build_with_lock()
    except Exception:  # noqa: BLE001
        log.exception("定时索引失败（不影响对话，下次到点重试）")
        return

    if res.get("skipped"):
        log.info("定时索引跳过：%s", res.get("reason"))
    else:
        log.info("定时索引完成：docs=%s removedStale=%s errors=%s 用时 %ss",
                 res.get("docs"), res.get("removedStale"),
                 res.get("errors"), res.get("elapsed"))


def _bootstrap_build() -> None:
    """启动自检：索引失效/缺失 → 建一次（在**后台线程**里跑，不阻塞服务启动）。"""
    try:
        st = indexer.index_status()
    except Exception as e:  # noqa: BLE001
        log.warning("索引自检失败（跳过启动构建）：%s", e)
        return

    if st.get("ok"):
        log.info("索引自检通过：%s 个文档（collection=%s）",
                 st.get("points"), config.RAG_COLLECTION)
        return

    reasons = "；".join(st.get("reasons") or [])
    need_force = bool(st.get("needForce"))
    log.warning("索引自检不通过（%s）→ 后台%s重建", reasons, "force " if need_force else "")
    try:
        res = indexer.build_with_lock(force=need_force)
        log.info("启动构建完成：docs=%s removedStale=%s errors=%s",
                 res.get("docs"), res.get("removedStale"), res.get("errors"))
    except Exception:  # noqa: BLE001
        log.exception("启动构建失败（不影响服务可用性）")


# ---------------------------------------------------------------- 生命周期

def startup() -> None:
    """FastAPI lifespan 启动时调用。`RAG_ENABLED=0` → 整体跳过（一键回退）。"""
    global _scheduler

    if not config.RAG_ENABLED:
        log.info("RAG_ENABLED=0 → 不启动定时索引（search_knowledge 走一键回退）")
        return

    if config.RAG_INDEX_ON_START:
        threading.Thread(target=_bootstrap_build, name="rag-bootstrap", daemon=True).start()

    if not _HAS_APS:
        log.warning("未安装 apscheduler → 定时索引不可用（pip install apscheduler）；"
                    "仍可手动跑 scripts/rag_reindex.py --full")
        return

    if _scheduler is not None:      # --reload 下 lifespan 可能被多次进入
        return

    try:
        trigger = CronTrigger.from_crontab(config.RAG_INDEX_CRON)
    except ValueError as e:
        log.error("RAG_INDEX_CRON 非法（%r）：%s → 不启动定时索引",
                  config.RAG_INDEX_CRON, e)
        return

    sched = AsyncIOScheduler()
    # 同步 job 会由 APScheduler 丢进线程池执行 → 不会卡住事件循环（SSE 照常流）
    sched.add_job(_job, trigger, id=JOB_ID, replace_existing=True,
                  max_instances=1, coalesce=True,   # 错过多次只补跑一次
                  misfire_grace_time=3600)          # 进程刚起/重启 1 小时内仍补跑
    sched.start()
    _scheduler = sched
    log.info("定时索引已启动：cron=%s（本地时区），下次触发 %s",
             config.RAG_INDEX_CRON, sched.get_job(JOB_ID).next_run_time)


def shutdown() -> None:
    """lifespan 退出时调用（`--reload` 下会反复进入，必须幂等）。"""
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
    except Exception:  # noqa: BLE001
        pass
    _scheduler = None


# ---------------------------------------------------------------- 诊断

def next_fire(expr: str | None = None, base: datetime | None = None) -> str | None:
    """按 cron 算下次触发时间（**只读**，不要求调度器在跑）——供 `--check` 展示。

    `--check` 是独立脚本、不会启动服务，所以不能靠 `status()["nextRunTime"]`。
    """
    if not _HAS_APS:
        return None
    try:
        trig = CronTrigger.from_crontab(expr or config.RAG_INDEX_CRON)
        return str(trig.get_next_fire_time(None, base or datetime.now()))
    except Exception:  # noqa: BLE001
        return None


def status() -> dict:
    """调度器现状（运维 / 验收脚本用）。索引时间同理**不向用户暴露**。"""
    info = {
        "enabled": config.RAG_ENABLED,
        "cron": config.RAG_INDEX_CRON,
        "onStart": config.RAG_INDEX_ON_START,
        "hasApscheduler": _HAS_APS,
        "running": _scheduler is not None,
        "jobId": JOB_ID,
    }
    job = _scheduler.get_job(JOB_ID) if _scheduler is not None else None
    info["nextRunTime"] = str(job.next_run_time) if job else next_fire()
    return info
