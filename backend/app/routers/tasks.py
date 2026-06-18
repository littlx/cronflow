"""任务注册与即时执行路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.registry import list_tasks
from app.schemas.task import TaskOut, TriggerTaskIn

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
async def get_tasks(user: CurrentUser = Depends(get_current_user)):
    """列出所有已注册任务 (不含 func 句柄)。"""
    return list_tasks()


@router.post("/trigger")
async def trigger_task(
    payload: TriggerTaskIn,
    user: CurrentUser = Depends(get_current_user),
):
    """立即触发一个任务 (异步, 经 Celery 执行)。"""
    from app.registry import get_task

    if not get_task(payload.task_id):
        raise HTTPException(status_code=404, detail=f"任务不存在: {payload.task_id}")

    from worker.celery_app import celery_app
    result = celery_app.send_task(
        "worker.run_python_task",
        kwargs={
            "task_id": payload.task_id,
            "trigger_type": "manual",
            "task_args": payload.task_args,
        },
    )
    return {"ok": True, "celery_id": result.id, "task_id": payload.task_id}
