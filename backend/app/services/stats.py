"""stats 物化服务 — Redis 计数器 (首版轻量方案)。

计数器: total / success / failed / running。由 worker 在执行前后 INCR/DECR 维护,
stats 接口直接读 Redis + 取最近 10 条日志, 替代旧版每 5 秒全表 count。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import async_redis, get_redis_stats_key
from app.models.schedule import JobSchedule
from app.models.task_log import TaskLog


async def _get_counter(metric: str) -> int:
    val = await async_redis.get(get_redis_stats_key(metric))
    return int(val) if val else 0


async def compute_stats(db: AsyncSession) -> dict:
    """组装一份完整的看板数据。"""
    total_tasks = 0
    try:
        from app.registry import TASKS
        total_tasks = len(TASKS)
    except Exception:
        pass

    total_schedules = (await db.execute(select(JobSchedule))).scalars().all()
    active = [s for s in total_schedules if s.enabled]

    total_runs = await _get_counter("total")
    success_runs = await _get_counter("success")
    failed_runs = await _get_counter("failed")
    running_runs = await _get_counter("running")

    finished = success_runs + failed_runs
    success_rate = round((success_runs / finished) * 100, 2) if finished > 0 else 0.0

    recent = (await db.execute(
        select(TaskLog).order_by(desc(TaskLog.started_at)).limit(10)
    )).scalars().all()

    # 系统指标
    try:
        import psutil
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
    except Exception:
        cpu = 0.0
        mem = 0.0

    return {
        "total_tasks": total_tasks,
        "total_schedules": len(total_schedules),
        "active_schedules": len(active),
        "total_runs": total_runs,
        "success_runs": success_runs,
        "failed_runs": failed_runs,
        "running_runs": running_runs,
        "success_rate": success_rate,
        "system": {"cpu_usage": cpu, "memory_usage": mem},
        "recent_logs": [r.to_dict() for r in recent],
    }


# ---- worker 同步维护计数器 (worker 进程用同步 redis) ----
def _incr(metric: str, n: int = 1) -> None:
    from app.core.redis import sync_redis
    sync_redis.incrby(get_redis_stats_key(metric), n)


def _decr(metric: str, n: int = 1) -> None:
    from app.core.redis import sync_redis
    sync_redis.decrby(get_redis_stats_key(metric), n)


def mark_running() -> None:
    _incr("running")
    _incr("total")


def mark_success() -> None:
    _decr("running")
    _incr("success")


def mark_failed() -> None:
    _decr("running")
    _incr("failed")


def reset_counters() -> dict:
    """重置计数器 (调试用)。"""
    from app.core.redis import sync_redis
    for m in ("total", "success", "failed", "running"):
        sync_redis.set(get_redis_stats_key(m), 0)
    return {"reset": True}
