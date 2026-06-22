"""stats 物化服务 — Redis 计数器 (首版轻量方案)。

计数器: total / success / failed / running。由 worker 在执行前后 INCR/DECR 维护,
stats 接口直接读 Redis + 取最近 10 条日志, 替代旧版每 5 秒全表 count。

本模块同时承担 prometheus gauge 同步刷新职责 (ACTIVE_SCHEDULES / REGISTERED_TASKS)。
异步 (compute_stats) 与同步 (compute_stats_sync) 共享 _assemble_payload, 防止两边漂移。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.redis import async_redis, get_redis_stats_key, sync_redis
from app.models.schedule import JobSchedule
from app.models.task_log import TaskLog


_METRICS = ("total", "success", "failed", "running")


# ---- 共享组装 ----

def _system_metrics() -> dict[str, float]:
    try:
        import psutil
        return {"cpu_usage": psutil.cpu_percent(), "memory_usage": psutil.virtual_memory().percent}
    except Exception:
        return {"cpu_usage": 0.0, "memory_usage": 0.0}


def _refresh_gauges(*, total_tasks: int, active_count: int) -> None:
    """每次组装顺手刷一下 prometheus gauge, 失败不影响主路径。"""
    try:
        from app.core.metrics import ACTIVE_SCHEDULES, REGISTERED_TASKS
        REGISTERED_TASKS.set(total_tasks)
        ACTIVE_SCHEDULES.set(active_count)
    except Exception:
        pass


def _assemble_payload(
    *,
    schedules: list,
    recent_logs: list[dict],
    counters: dict[str, int],
    total_tasks: int,
    system: dict[str, float],
) -> dict:
    active = [s for s in schedules if s.enabled]
    success = counters["success"]
    failed = counters["failed"]
    finished = success + failed
    rate = round((success / finished) * 100, 2) if finished > 0 else 0.0

    _refresh_gauges(total_tasks=total_tasks, active_count=len(active))

    return {
        "total_tasks": total_tasks,
        "total_schedules": len(schedules),
        "active_schedules": len(active),
        "total_runs": counters["total"],
        "success_runs": success,
        "failed_runs": failed,
        "running_runs": counters["running"],
        "success_rate": rate,
        "system": system,
        "recent_logs": recent_logs,
    }


def _read_counters_sync() -> dict[str, int]:
    return {m: int(sync_redis.get(get_redis_stats_key(m)) or 0) for m in _METRICS}


async def _read_counters_async() -> dict[str, int]:
    keys = [get_redis_stats_key(m) for m in _METRICS]
    vals = await async_redis.mget(*keys)
    return dict(zip(_METRICS, [int(v or 0) for v in vals]))


# ---- 入口 ----

async def compute_stats(db: AsyncSession) -> dict:
    """API / 异步路径: 组装看板数据。"""
    from app.registry import TASKS

    schedules = (await db.execute(select(JobSchedule))).scalars().all()
    recent = (await db.execute(
        select(TaskLog).order_by(desc(TaskLog.started_at)).limit(10)
    )).scalars().all()
    return _assemble_payload(
        schedules=list(schedules),
        recent_logs=[r.to_dict() for r in recent],
        counters=await _read_counters_async(),
        total_tasks=len(TASKS),
        system=_system_metrics(),
    )


def compute_stats_sync(session: Session) -> dict:
    """worker / 同步路径: 与 compute_stats 完全一致的载荷。"""
    from app.registry import TASKS

    schedules = session.execute(select(JobSchedule)).scalars().all()
    recent = session.execute(
        select(TaskLog).order_by(desc(TaskLog.started_at)).limit(10)
    ).scalars().all()
    return _assemble_payload(
        schedules=list(schedules),
        recent_logs=[r.to_dict() for r in recent],
        counters=_read_counters_sync(),
        total_tasks=len(TASKS),
        system=_system_metrics(),
    )


# ---- worker 同步维护计数器 (worker 进程用同步 redis) ----

def _incr(metric: str, n: int = 1) -> None:
    sync_redis.incrby(get_redis_stats_key(metric), n)


def _decr(metric: str, n: int = 1) -> None:
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
    """重置计数器 (调试/清空日志)。"""
    for m in _METRICS:
        sync_redis.set(get_redis_stats_key(m), 0)
    return {"reset": True}
