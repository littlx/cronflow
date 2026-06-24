"""缓存视图(列展示)配置 CRUD 路由。

- GET    /api/cache-views/{collection}  → 获取配置 (404 表示尚未配置)
- PUT    /api/cache-views/{collection}  → upsert 配置
- DELETE /api/cache-views/{collection}  → 删除配置
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models.cache_view_config import CacheViewConfig
from app.schemas.cache_view import CacheViewConfigOut, CacheViewConfigUpsert

router = APIRouter(prefix="/api/cache-views", tags=["cache-views"])


@router.get("/{target_collection}", response_model=CacheViewConfigOut)
async def get_view_config(
    target_collection: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(CacheViewConfig).where(
                CacheViewConfig.target_collection == target_collection
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="尚未配置")
    return row.to_dict()


@router.put("/{target_collection}", response_model=CacheViewConfigOut)
async def upsert_view_config(
    target_collection: str,
    payload: CacheViewConfigUpsert,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(CacheViewConfig).where(
                CacheViewConfig.target_collection == target_collection
            )
        )
    ).scalar_one_or_none()

    columns_data = [c.model_dump() for c in payload.columns]
    if row is None:
        row = CacheViewConfig(
            target_collection=target_collection,
            row_path=payload.row_path or "",
            columns=columns_data,
        )
        db.add(row)
    else:
        row.row_path = payload.row_path or ""
        row.columns = columns_data
    await db.commit()
    await db.refresh(row)
    return row.to_dict()


@router.delete("/{target_collection}")
async def delete_view_config(
    target_collection: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(CacheViewConfig).where(
                CacheViewConfig.target_collection == target_collection
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="尚未配置")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
