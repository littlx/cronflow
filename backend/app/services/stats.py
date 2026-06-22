"""stats 服务 — SQLite count + 启动 reconciliation。

无 Redis 计数器, 直接 SELECT count(*) GROUP BY status, 3 人量级毫秒级。
启动时 reconciliation: 把 status='running' 且超时的日志标 failed,
修复进程崩溃导致的 running 残留 (解决旧版计数器泄漏问题)。

同时这里负责刷新 prometheus gauge (ACTIVE_SCHEDULES / REGISTERED_TASKS),
每次 compute_stats 顺手调一次。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.metrics import ACTIVE_SCHEDULES, REGISTERED_TASKS
from app.models.schedule import JobSchedule
from app.models.task_log import TaskLog


def _system_metrics() -> dict[str, float]:
    try:
        import psutil
        return {"cpu_usage": psutil.cpu_percent(), "memory_usage": psutil.virtual_memory().percent}
    except Exception:
        return {"cpu_usage": 0.0, "memory_usage": 0.0}


def _refresh_gauges(total_tasks: int, active_count: int) -> None:
    """顺手刷一下 prometheus gauge, 失败绝不影响主路径。"""
    try:
        REGISTERED_TASKS.set(total_tasks)
        ACTIVE_SCHEDULES.set(active_count)
    except Exception:
        pass


async def reconcile_running_logs(db: AsyncSession) -> int:
    """启动 reconciliation: 把超时的 running 日志标 failed。

    判定: started_at 超过 task_default_timeout * (retry_max+1) 秒仍为 running,
    视为进程崩溃残留, 标记 failed。
    返回修复的行数。
    """
    threshold = datetime.now(timezone.utc) - timedelta(
        seconds=settings.task_default_timeout * (settings.task_retry_max + 1) * 2
    )
    result = await db.execute(
        update(TaskLog)
        .where(TaskLog.status == "running")
        .where(TaskLog.started_at < threshold)
        .values(status="failed", error="reconciled: process crash (running timeout)", finished_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return result.rowcount or 0


async def compute_stats(db: AsyncSession) -> dict:
    """组装看板数据: 计数器 + 调度数 + 最近日志 + 系统指标。"""
    from app.registry import TASKS

    # 计数器: GROUP BY status, 一次查询
    counts_rows = await db.execute(
        select(TaskLog.status, func.count(TaskLog.id)).group_by(TaskLog.status)
    )
    counts = {row[0]: row[1] for row in counts_rows}
    total = sum(counts.values())
    success = counts.get("success", 0)
    failed = counts.get("failed", 0)
    running = counts.get("running", 0)
    finished = success + failed
    rate = round((success / finished) * 100, 2) if finished > 0 else 0.0

    # 调度数
    schedules = (await db.execute(select(JobSchedule))).scalars().all()
    active = [s for s in schedules if s.enabled]

    # 最近 10 条日志
    recent = (
        await db.execute(select(TaskLog).order_by(desc(TaskLog.started_at)).limit(10))
    ).scalars().all()

    # 顺手刷 prometheus gauge
    _refresh_gauges(total_tasks=len(TASKS), active_count=len(active))

    return {
        "total_tasks": len(TASKS),
        "total_schedules": len(schedules),
        "active_schedules": len(active),
        "total_runs": total,
        "success_runs": success,
        "failed_runs": failed,
        "running_runs": running,
        "success_rate": rate,
        "system": _system_metrics(),
        "recent_logs": [r.to_dict() for r in recent],
    }
