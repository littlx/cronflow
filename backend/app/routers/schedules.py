"""定时调度 CRUD 路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.schemas.schedule import ScheduleCreate, ScheduleOut, ScheduleUpdate
from app.services import schedule_service

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _enrich(d: dict, schedule_id: int, enabled: bool) -> dict:
    """从 redbeat 读 due_at 覆盖 DB 中不可靠的 next_run_time。"""
    if not enabled:
        d["next_run_time"] = None
        return d
    try:
        from scheduler.beat import get_next_run_time
        nrt = get_next_run_time(schedule_id)
        if nrt:
            d["next_run_time"] = nrt
    except Exception:
        pass
    return d


@router.get("", response_model=list[ScheduleOut])
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    rows = await schedule_service.list_schedules(db)
    return [_enrich(r.to_dict(), r.id, r.enabled) for r in rows]


@router.post("", response_model=ScheduleOut)
async def create_schedule(
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    sched = await schedule_service.create_schedule(db, payload)
    return _enrich(sched.to_dict(), sched.id, sched.enabled)


@router.put("/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    sched = await schedule_service.update_schedule(db, schedule_id, payload)
    if not sched:
        raise HTTPException(status_code=404, detail="调度不存在")
    return _enrich(sched.to_dict(), sched.id, sched.enabled)


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    ok = await schedule_service.delete_schedule(db, schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="调度不存在")
    return {"ok": True}


@router.post("/{schedule_id}/toggle", response_model=ScheduleOut)
async def toggle_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    sched = await schedule_service.toggle_schedule(db, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="调度不存在")
    return _enrich(sched.to_dict(), sched.id, sched.enabled)
