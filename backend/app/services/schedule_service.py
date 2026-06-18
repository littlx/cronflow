"""调度业务逻辑层 — 协调 DB 写入 + redbeat entry 同步 + 事件推送。

不再区分 python/curl 任务。schedule.task_ref 是统一字符串引用。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import JobSchedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate


async def list_schedules(db: AsyncSession) -> list[JobSchedule]:
    rows = (await db.execute(select(JobSchedule).order_by(JobSchedule.id))).scalars().all()
    return list(rows)


async def create_schedule(db: AsyncSession, payload: ScheduleCreate) -> JobSchedule:
    sched = JobSchedule(
        task_ref=payload.task_ref,
        name=payload.name,
        trigger_type=payload.trigger_type,
        trigger_args=payload.trigger_args,
        task_args=payload.task_args,
        enabled=payload.enabled,
    )
    db.add(sched)
    await db.commit()
    await db.refresh(sched)

    if payload.enabled:
        try:
            from scheduler.beat import upsert_schedule_entry
            key = upsert_schedule_entry(
                schedule_id=sched.id,
                task_ref=sched.task_ref,
                trigger_type=sched.trigger_type,
                trigger_args=sched.trigger_args,
                task_args=sched.task_args,
                enabled=True,
            )
            sched.redbeat_key = key
            await db.commit()
            await db.refresh(sched)
        except Exception as e:
            print(f"[schedule] redbeat sync failed on create: {e}")

    _notify_changed()
    return sched


async def update_schedule(db: AsyncSession, schedule_id: int, payload: ScheduleUpdate) -> JobSchedule | None:
    sched = await db.get(JobSchedule, schedule_id)
    if not sched:
        return None

    changed = False
    if payload.name is not None:
        sched.name = payload.name
    if payload.trigger_type is not None:
        sched.trigger_type = payload.trigger_type
        changed = True
    if payload.trigger_args is not None:
        sched.trigger_args = payload.trigger_args
        changed = True
    if payload.task_args is not None:
        sched.task_args = payload.task_args
    if payload.enabled is not None:
        sched.enabled = payload.enabled
        changed = True

    await db.commit()
    await db.refresh(sched)

    if changed:
        try:
            from scheduler.beat import delete_schedule_entry, upsert_schedule_entry
            if sched.enabled:
                key = upsert_schedule_entry(
                    schedule_id=sched.id,
                    task_ref=sched.task_ref,
                    trigger_type=sched.trigger_type,
                    trigger_args=sched.trigger_args,
                    task_args=sched.task_args,
                    enabled=True,
                )
                sched.redbeat_key = key
            else:
                delete_schedule_entry(sched.id)
                sched.redbeat_key = None
            await db.commit()
            await db.refresh(sched)
        except Exception as e:
            print(f"[schedule] redbeat sync failed on update: {e}")

    _notify_changed()
    return sched


async def delete_schedule(db: AsyncSession, schedule_id: int) -> bool:
    sched = await db.get(JobSchedule, schedule_id)
    if not sched:
        return False
    try:
        from scheduler.beat import delete_schedule_entry
        delete_schedule_entry(sched.id)
    except Exception as e:
        print(f"[schedule] redbeat delete failed: {e}")
    await db.delete(sched)
    await db.commit()
    _notify_changed()
    return True


async def toggle_schedule(db: AsyncSession, schedule_id: int) -> JobSchedule | None:
    sched = await db.get(JobSchedule, schedule_id)
    if not sched:
        return None
    sched.enabled = not sched.enabled
    await db.commit()
    await db.refresh(sched)
    try:
        from scheduler.beat import delete_schedule_entry, upsert_schedule_entry
        if sched.enabled:
            key = upsert_schedule_entry(
                schedule_id=sched.id,
                task_ref=sched.task_ref,
                trigger_type=sched.trigger_type,
                trigger_args=sched.trigger_args,
                task_args=sched.task_args,
                enabled=True,
            )
            sched.redbeat_key = key
        else:
            delete_schedule_entry(sched.id)
            sched.redbeat_key = None
        await db.commit()
        await db.refresh(sched)
    except Exception as e:
        print(f"[schedule] redbeat toggle failed: {e}")
    _notify_changed()
    return sched


def _notify_changed() -> None:
    try:
        from app.core.eventbus_sync import emit_schedule_changed
        emit_schedule_changed()
    except Exception as e:
        print(f"[schedule] notify changed failed: {e}")
