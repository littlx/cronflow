"""调度循环 — 替代 beat + redbeat。

单进程 asyncio 循环, 每 N 秒扫表, 到点的投递执行。
next_run_time 是 DB 真相源, 不依赖外部调度器。

启动时:
- ensure_default_schedules: 注册默认的日志/缓存清理调度 (若不存在),
  防止数据无限增长 (修复旧版「TTL 任务存在但无调度」的问题)。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.schedule import JobSchedule
from app.services.executor import get_executor
from app.services.schedule_service import compute_next_run

logger = get_logger("scheduler")


# 默认调度: 启动时自动注册, 名字唯一识别 (按 task_ref + 系统标签)
_DEFAULT_SCHEDULES = [
    {
        "task_ref": "tasks.system_tasks.cleanup_old_logs",
        "name": "[系统] 每日清理过期日志",
        "trigger_type": "cron",
        "trigger_args": {"minute": "0", "hour": "3"},  # 每日 03:00
        "task_args": {"keep_days": settings.log_retention_days},
    },
    {
        "task_ref": "tasks.system_tasks.cleanup_old_cache",
        "name": "[系统] 每日清理过期缓存",
        "trigger_type": "cron",
        "trigger_args": {"minute": "30", "hour": "3"},  # 每日 03:30
        "task_args": {"keep_days": settings.cache_retention_days},
    },
]


async def ensure_default_schedules() -> None:
    """启动时确保默认调度存在 (按 task_ref + name 幂等检查)。

    用户可手动禁用/删除这些调度, 此函数不会复活已被用户删除的调度
    (仅当 name 完全不存在时才创建)。
    """
    async with AsyncSessionLocal() as db:
        for cfg in _DEFAULT_SCHEDULES:
            existing = (
                await db.execute(
                    select(JobSchedule).where(JobSchedule.name == cfg["name"])
                )
            ).scalar_one_or_none()
            if existing:
                continue
            sched = JobSchedule(
                task_ref=cfg["task_ref"],
                name=cfg["name"],
                trigger_type=cfg["trigger_type"],
                trigger_args=cfg["trigger_args"],
                task_args=cfg["task_args"],
                enabled=True,
            )
            sched.next_run_time = compute_next_run(sched)
            db.add(sched)
            logger.info("default schedule created", name=cfg["name"])
        await db.commit()


async def scheduler_loop() -> None:
    """每 tick 秒扫描 schedules 表, 到点的投递执行。

    异常兜底 + continue, 循环挂不掉。单实例部署下这是唯一的调度驱动。
    """
    logger.info("scheduler loop started", tick=settings.scheduler_tick_seconds)
    while True:
        try:
            now = datetime.now(timezone.utc)
            async with AsyncSessionLocal() as db:
                due = await db.execute(
                    select(JobSchedule)
                    .where(JobSchedule.enabled.is_(True))
                    .where(JobSchedule.next_run_time <= now)
                )
                for sched in due.scalars():
                    # 先重算 next_run_time, 避免循环内重复投递同一行
                    sched.next_run_time = compute_next_run(sched, base=now)
                    triggered_at = now.strftime("%Y%m%dT%H%M%S")
                    await db.commit()

                    # 非阻塞投递到 executor 协程池
                    executor = get_executor()
                    asyncio.create_task(executor.run(
                        task_ref=sched.task_ref,
                        trigger_type=sched.trigger_type,
                        task_args=sched.task_args or {},
                        schedule_id=sched.id,
                        triggered_at=triggered_at,
                    ))
                    logger.info(
                        "schedule triggered", schedule_id=sched.id,
                        task_ref=sched.task_ref, next_run=sched.next_run_time,
                    )
        except Exception:
            logger.exception("scheduler_loop tick failed")
        await asyncio.sleep(settings.scheduler_tick_seconds)
