"""缓存数据查询路由 — curl handler 写入的 JSON 缓存。分页查询。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models.cache import CrawledDataCache

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("/{target_collection}")
async def get_cache(
    target_collection: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """按 target_collection 分页查询缓存数据, 时间倒序。"""
    base = select(CrawledDataCache).where(CrawledDataCache.target_collection == target_collection)
    count_base = select(func.count(CrawledDataCache.id)).where(
        CrawledDataCache.target_collection == target_collection
    )

    total = (await db.execute(count_base)).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(desc(CrawledDataCache.created_at)).offset(offset).limit(limit)
        )
    ).scalars().all()

    return {
        "items": [r.to_dict() for r in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }
