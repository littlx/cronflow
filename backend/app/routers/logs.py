"""执行日志路由。

GET /api/logs 支持:
- 过滤: task_ref / status / started_after / started_before
- 翻页: limit (1~500) + offset (≥0)
返回 {items, total, limit, offset} 便于前端做分页 UI。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models.task_log import TaskLog

router = APIRouter(prefix="/api/logs", tags=["logs"])


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # 允许 'Z' 结尾
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"非法时间: {s} ({e})")


@router.get("")
async def get_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    task_ref: str | None = Query(None, description="按任务 ref 过滤"),
    status: str | None = Query(None, description="running | success | failed"),
    started_after: str | None = Query(None, description="ISO 时间, 含此刻之后"),
    started_before: str | None = Query(None, description="ISO 时间, 不含此刻"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """查询执行日志, 支持过滤 + 分页 + 时间范围。"""
    base = select(TaskLog)
    count_base = select(func.count(TaskLog.id))

    after_dt = _parse_iso(started_after)
    before_dt = _parse_iso(started_before)

    for stmt in (base, count_base):
        pass  # placeholder for type checker

    def _where(stmt):
        if task_ref:
            stmt = stmt.where(TaskLog.task_ref == task_ref)
        if status:
            stmt = stmt.where(TaskLog.status == status)
        if after_dt is not None:
            stmt = stmt.where(TaskLog.started_at >= after_dt)
        if before_dt is not None:
            stmt = stmt.where(TaskLog.started_at < before_dt)
        return stmt

    total = (await db.execute(_where(count_base))).scalar() or 0

    rows = (
        await db.execute(
            _where(base).order_by(desc(TaskLog.started_at)).offset(offset).limit(limit)
        )
    ).scalars().all()

    return {
        "items": [r.to_dict() for r in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


@router.post("/clear")
async def clear_logs(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """清空所有日志, 同时重置 stats 计数器, 避免出现「日志为空但 total/success 非 0」的不一致。"""
    await db.execute(delete(TaskLog))
    await db.commit()
    # Redis 计数器与日志表是两份真相; 清空日志必须同步清零, 否则 dashboard 仍显示历史值
    from app.services.stats import compute_stats, reset_counters
    reset_counters()
    # 主动广播一次空 stats, 让前端立刻刷新
    try:
        from app.core.eventbus import EVENT_STATS_UPDATE, emit
        await emit(EVENT_STATS_UPDATE, await compute_stats(db))
    except Exception:
        pass
    return {"ok": True}
