"""缓存数据查询路由 — curl handler 写入的 JSON 缓存。

upsert 语义: 每个 target_collection 最多一条缓存记录 (handler 删除旧+插新)。
提供两个查询方式:
  GET /{collection}        — 分页查询 (兼容旧版, 但值只有 0/1 条)
  GET /{collection}/latest — 单条最近缓存, 直接返回 document (最常用)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
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
    """按 target_collection 分页查询缓存数据 (upsert 语义下最多 1 条)。"""
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


@router.get("/{target_collection}/latest")
async def get_latest_cache(
    target_collection: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """获取指定 collection 的最新一条缓存 (document 直接返回)。"""
    row = (
        await db.execute(
            select(CrawledDataCache)
            .where(CrawledDataCache.target_collection == target_collection)
            .order_by(desc(CrawledDataCache.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="没有缓存数据")
    return row.to_dict()