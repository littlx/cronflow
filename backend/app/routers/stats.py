"""监控统计路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.services.stats import compute_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """返回看板所需的完整统计数据。"""
    return await compute_stats(db)
