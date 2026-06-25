"""调度业务逻辑层 — CRUD + next_run_time 重算。

不再依赖 redbeat, next_run_time 是 DB 真相源, 调度循环扫表 WHERE next_run_time <= now()。
创建/更新/启停时由本模块用 croniter 重算 next_run_time。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from croniter import croniter
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.schedule import JobSchedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate

logger = get_logger("schedule_service")


def compute_next_run(sched: JobSchedule, base: datetime | None = None) -> datetime | None:
    """根据 trigger_type/trigger_args 计算下一次运行时间 (UTC)。"""
    if not sched.enabled:
        return None
    base = base or datetime.now(timezone.utc)
    args = {k: v for k, v in (sched.trigger_args or {}).items() if v is not None and v != ""}

    if sched.trigger_type == "interval":
        seconds = 0
        for unit, factor in (("seconds", 1), ("minutes", 60), ("hours", 3600), ("days", 86400)):
            if unit in args:
                seconds = int(args[unit]) * factor
                break
        if seconds <= 0:
            seconds = 300
        next_run = base + timedelta(seconds=seconds)

        start_time = args.get("start_time")
        end_time = args.get("end_time")
        if start_time and end_time:
            try:
                sh, sm = map(int, start_time.split(":")[:2])
                eh, em = map(int, end_time.split(":")[:2])
                nr_local = next_run.astimezone()
                start_dt = nr_local.replace(hour=sh, minute=sm, second=0, microsecond=0)
                end_dt = nr_local.replace(hour=eh, minute=em, second=0, microsecond=0)
                if start_dt <= end_dt:
                    if nr_local < start_dt:
                        nr_local = start_dt
                    elif nr_local > end_dt:
                        nr_local = start_dt + timedelta(days=1)
                else:
                    if end_dt < nr_local < start_dt:
                        nr_local = start_dt
                next_run = nr_local.astimezone(timezone.utc)
            except Exception as e:
                logger.warning("invalid active time range constraint", start=start_time, end=end_time, error=str(e))
        return next_run

    if sched.trigger_type == "cron":
        minute = args.get("minute", "*")
        hour = args.get("hour", "*")
        day = args.get("day", args.get("day_of_month", "*"))
        month = args.get("month", args.get("month_of_year", "*"))
        week = args.get("day_of_week", "*")
        expr = f"{minute} {hour} {day} {month} {week}"
        try:
            cron = croniter(expr, base)
            return cron.get_next(datetime)
        except Exception as e:
            logger.warning("invalid cron expr", expr=expr, error=str(e))
            return None

    return None


async def _resolve_or_404(db: AsyncSession, ref: str):
    from app.services.ref_resolver import resolve_ref
    r = await resolve_ref(db, ref)
    if not r:
        raise HTTPException(status_code=404, detail=f"task_ref 不存在: {ref}")
    return r


def _validate_or_422(resolved, task_args: dict[str, Any]) -> None:
    from app.services.task_service import validate_task_args
    errors = validate_task_args(resolved, task_args)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})


async def list_schedules(db: AsyncSession) -> list[JobSchedule]:
    rows = (await db.execute(select(JobSchedule).order_by(JobSchedule.id))).scalars().all()
    return list(rows)


async def create_schedule(db: AsyncSession, payload: ScheduleCreate) -> JobSchedule:
    resolved = await _resolve_or_404(db, payload.task_ref)
    _validate_or_422(resolved, payload.task_args)

    sched = JobSchedule(
        task_ref=payload.task_ref,
        name=payload.name,
        trigger_type=payload.trigger_type,
        trigger_args=payload.trigger_args,
        task_args=payload.task_args,
        enabled=payload.enabled,
    )
    sched.next_run_time = compute_next_run(sched)
    db.add(sched)
    await db.commit()
    await db.refresh(sched)
    return sched


async def update_schedule(db: AsyncSession, schedule_id: int, payload: ScheduleUpdate) -> JobSchedule | None:
    sched = await db.get(JobSchedule, schedule_id)
    if not sched:
        return None

    if payload.name is not None:
        sched.name = payload.name
    if payload.trigger_type is not None:
        sched.trigger_type = payload.trigger_type
    if payload.trigger_args is not None:
        sched.trigger_args = payload.trigger_args
    if payload.task_args is not None:
        sched.task_args = payload.task_args
    if payload.enabled is not None:
        sched.enabled = payload.enabled

    if payload.task_args is not None:
        resolved = await _resolve_or_404(db, sched.task_ref)
        _validate_or_422(resolved, sched.task_args)

    sched.next_run_time = compute_next_run(sched)
    await db.commit()
    await db.refresh(sched)
    return sched


async def delete_schedule(db: AsyncSession, schedule_id: int) -> bool:
    sched = await db.get(JobSchedule, schedule_id)
    if not sched:
        return False
    await db.delete(sched)
    await db.commit()
    return True


async def toggle_schedule(db: AsyncSession, schedule_id: int) -> JobSchedule | None:
    sched = await db.get(JobSchedule, schedule_id)
    if not sched:
        return None
    sched.enabled = not sched.enabled
    sched.next_run_time = compute_next_run(sched)
    await db.commit()
    await db.refresh(sched)
    return sched
