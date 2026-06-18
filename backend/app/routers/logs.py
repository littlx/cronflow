"""执行日志路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models.task_log import TaskLog

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
async def get_logs(
    limit: int = Query(100, ge=1, le=500),
    task_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """查询执行日志, 支持按任务/状态过滤。"""
    stmt = select(TaskLog).order_by(desc(TaskLog.started_at)).limit(limit)
    if task_id:
        stmt = stmt.where(TaskLog.task_id == task_id)
    if status:
        stmt = stmt.where(TaskLog.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return [r.to_dict() for r in rows]


@router.post("/clear")
async def clear_logs(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """清空所有日志。"""
    await db.execute(delete(TaskLog))
    await db.commit()
    return {"ok": True}
