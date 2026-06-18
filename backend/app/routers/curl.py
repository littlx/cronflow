"""cURL 同步任务 + 缓存数据 路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models.cache import CrawledDataCache
from app.schemas.curl import CurlTaskCreate, CurlTaskOut, CurlTaskUpdate
from app.services import curl_service

router = APIRouter(prefix="/api/curl-tasks", tags=["curl"])


@router.get("", response_model=list[CurlTaskOut])
async def list_curl_tasks(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    rows = await curl_service.list_curl_tasks(db)
    return [r.to_dict() for r in rows]


@router.post("", response_model=CurlTaskOut)
async def create_curl_task(
    payload: CurlTaskCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    curl = await curl_service.create_curl_task(db, payload)
    return curl.to_dict()


@router.put("/{task_id}", response_model=CurlTaskOut)
async def update_curl_task(
    task_id: str,
    payload: CurlTaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    curl = await curl_service.update_curl_task(db, task_id, payload)
    if not curl:
        raise HTTPException(status_code=404, detail="cURL 任务不存在")
    return curl.to_dict()


@router.delete("/{task_id}")
async def delete_curl_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    ok = await curl_service.delete_curl_task(db, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="cURL 任务不存在")
    return {"ok": True}


@router.post("/{task_id}/trigger")
async def trigger_curl_task(
    task_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    celery_id = await curl_service.trigger_curl_task(task_id)
    return {"ok": True, "celery_id": celery_id, "task_id": task_id}


@router.get("/data/{target_collection}")
async def get_cache_data(
    target_collection: str,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """查询某 collection 的缓存数据, 按时间倒序。"""
    rows = (
        await db.execute(
            select(CrawledDataCache)
            .where(CrawledDataCache.target_collection == target_collection)
            .order_by(desc(CrawledDataCache.created_at))
            .limit(limit)
        )
    ).scalars().all()
    return [r.to_dict() for r in rows]
