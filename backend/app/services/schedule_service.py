"""调度业务逻辑层 — 协调 DB 写入 + redbeat entry 同步 + 事件推送。

不再区分 python/curl 任务。schedule.task_ref 是统一字符串引用。
创建/更新前会先解析 task_ref 并校验 task_args; redbeat 的 queue/priority
取自 resolved task (python: register_task 装饰器; curl: handler_config)。
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import JobSchedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate


async def _resolve_or_404(db: AsyncSession, ref: str):
    from app.services.ref_resolver import resolve_ref_async
    r = await resolve_ref_async(db, ref)
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
    db.add(sched)
    await db.commit()
    await db.refresh(sched)

    if payload.enabled:
        try:
            from scheduler.beat import upsert_schedule_entry
            upsert_schedule_entry(
                schedule_id=sched.id,
                task_ref=sched.task_ref,
                trigger_type=sched.trigger_type,
                trigger_args=sched.trigger_args,
                task_args=sched.task_args,
                enabled=True,
                queue=resolved.queue,
                priority=resolved.priority,
            )
        except Exception as e:
            print(f"[schedule] redbeat sync failed on create: {e}")

    _notify_changed("created", sched.id)
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

    # 改了 task_args 也要校验
    if payload.task_args is not None:
        resolved = await _resolve_or_404(db, sched.task_ref)
        _validate_or_422(resolved, sched.task_args)

    await db.commit()
    await db.refresh(sched)

    if changed:
        try:
            resolved = await _resolve_or_404(db, sched.task_ref)
            from scheduler.beat import delete_schedule_entry, upsert_schedule_entry
            if sched.enabled:
                upsert_schedule_entry(
                    schedule_id=sched.id,
                    task_ref=sched.task_ref,
                    trigger_type=sched.trigger_type,
                    trigger_args=sched.trigger_args,
                    task_args=sched.task_args,
                    enabled=True,
                    queue=resolved.queue,
                    priority=resolved.priority,
                )
            else:
                delete_schedule_entry(sched.id)
        except Exception as e:
            print(f"[schedule] redbeat sync failed on update: {e}")

    _notify_changed("updated", sched.id)
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
    sid = sched.id
    await db.delete(sched)
    await db.commit()
    _notify_changed("deleted", sid)
    return True


async def toggle_schedule(db: AsyncSession, schedule_id: int) -> JobSchedule | None:
    sched = await db.get(JobSchedule, schedule_id)
    if not sched:
        return None
    sched.enabled = not sched.enabled
    await db.commit()
    await db.refresh(sched)
    try:
        resolved = await _resolve_or_404(db, sched.task_ref)
        from scheduler.beat import delete_schedule_entry, upsert_schedule_entry
        if sched.enabled:
            upsert_schedule_entry(
                schedule_id=sched.id,
                task_ref=sched.task_ref,
                trigger_type=sched.trigger_type,
                trigger_args=sched.trigger_args,
                task_args=sched.task_args,
                enabled=True,
                queue=resolved.queue,
                priority=resolved.priority,
            )
        else:
            delete_schedule_entry(sched.id)
    except Exception as e:
        print(f"[schedule] redbeat toggle failed: {e}")
    _notify_changed("toggled", sched.id)
    return sched


def _notify_changed(action: str, schedule_id: int | None) -> None:
    """发 schedule_changed 事件, 携带操作信息让前端可做局部刷新。"""
    try:
        from app.core.eventbus_sync import emit_schedule_changed
        emit_schedule_changed({"action": action, "id": schedule_id})
        # gauge 刷新不强制成功
        try:
            _refresh_active_gauge()
        except Exception:
            pass
    except Exception as e:
        print(f"[schedule] notify changed failed: {e}")


def _refresh_active_gauge() -> None:
    """同步刷新 ACTIVE_SCHEDULES gauge (调度增删启停时)。"""
    from app.core.db_sync import get_sync_session
    from app.core.metrics import ACTIVE_SCHEDULES
    session = get_sync_session()
    try:
        rows = session.execute(select(JobSchedule).where(JobSchedule.enabled.is_(True))).scalars().all()
        ACTIVE_SCHEDULES.set(len(list(rows)))
    finally:
        session.close()
