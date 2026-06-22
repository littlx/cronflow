"""统一任务路由 — python (只读, 来自注册表) + curl (CRUD, 入库) + 触发。

路由顺序约定: 所有具体路径 (`/curl`, `/curl/{id}`, `/trigger`) 必须排在
通配 `GET /{ref:path}` 之前, 否则后者会吞掉所有同方法子路径。
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.schemas.task import (
    CurlTaskCreate,
    CurlTaskUpdate,
    TaskOut,
    TriggerTaskIn,
)
from app.services import task_service
from app.services.executor import get_executor
from app.services.ref_resolver import resolve_ref

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    kind: str | None = Query(None, description="过滤 kind: python | curl"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return await task_service.list_all_tasks(db, kind=kind)


# ---- 具体路径优先 ----

@router.post("/curl", response_model=TaskOut)
async def create_curl_task(
    payload: CurlTaskCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """创建一个 curl 任务 (kind='curl')。python 任务通过 @register_task 注册, 不走 API。"""
    return await task_service.create_curl_task(db, payload.model_dump())


@router.put("/curl/{task_id}", response_model=TaskOut)
async def update_curl_task(
    task_id: str,
    payload: CurlTaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    view = await task_service.update_curl_task(db, task_id, payload.model_dump(exclude_unset=True))
    if not view:
        raise HTTPException(status_code=404, detail="curl 任务不存在")
    return view


@router.delete("/curl/{task_id}")
async def delete_curl_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    ok = await task_service.delete_curl_task(db, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="curl 任务不存在")
    return {"ok": True}


@router.post("/trigger")
async def trigger_task(
    payload: TriggerTaskIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """立即触发任意 kind 的任务 (异步, 经 executor 协程池执行)。"""
    resolved = await resolve_ref(db, payload.task_ref)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"任务不存在: {payload.task_ref}")

    # 触发前校验任务参数 (python 任务 required 字段, 类型)
    from app.services.task_service import validate_task_args
    errors = validate_task_args(resolved, payload.task_args)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    # 非阻塞投递到 executor 协程池
    executor = get_executor()
    asyncio.create_task(executor.run(
        task_ref=payload.task_ref,
        trigger_type="manual",
        task_args=payload.task_args,
    ))
    return {"ok": True, "task_ref": payload.task_ref, "kind": resolved.kind}


# ---- 通配兜底, 放最后 ----

@router.get("/{ref:path}", response_model=TaskOut)
async def get_task(
    ref: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    view = await task_service.get_task_view(db, ref)
    if not view:
        raise HTTPException(status_code=404, detail=f"任务不存在: {ref}")
    return view
