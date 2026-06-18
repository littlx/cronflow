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
    """清空所有日志, 同时重置 stats 计数器, 避免出现「日志为空但 total/success 非 0」的不一致。"""
    await db.execute(delete(TaskLog))
    await db.commit()
    # Redis 计数器与日志表是两份真相; 清空日志必须同步清零, 否则 dashboard 仍显示历史值
    from app.services.stats import reset_counters
    reset_counters()
    # 主动广播一次空 stats, 让前端立刻刷新
    try:
        from app.core.eventbus import EVENT_STATS_UPDATE, emit
        await emit(EVENT_STATS_UPDATE, await _compute_stats_payload(db))
    except Exception:
        pass
    return {"ok": True}


async def _compute_stats_payload(db: AsyncSession) -> dict:
    from app.services.stats import compute_stats
    return await compute_stats(db)
