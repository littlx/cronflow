"""调度循环 — 替代 beat + redbeat。

单进程 asyncio 循环, 每 N 秒扫表, 到点的投递执行。
next_run_time 是 DB 真相源, 不依赖外部调度器。
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
