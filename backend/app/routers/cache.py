"""缓存数据查询路由 — curl handler 写入的 JSONB 缓存。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models.cache import CrawledDataCache

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("/{target_collection}")
async def get_cache(
    target_collection: str,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """按 target_collection 查询缓存数据, 时间倒序。"""
    rows = (
        await db.execute(
            select(CrawledDataCache)
            .where(CrawledDataCache.target_collection == target_collection)
            .order_by(desc(CrawledDataCache.created_at))
            .limit(limit)
        )
    ).scalars().all()
    return [r.to_dict() for r in rows]
