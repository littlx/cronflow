"""cURL 任务业务逻辑层 — DB 写入 + redbeat 轮询调度 + 事件推送。

每个 curl_task 对应一个 redbeat interval 调度 (每 minutes 分钟触发 run_curl_task)。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curl_task import CurlTask
from app.schemas.curl import CurlTaskCreate, CurlTaskUpdate

# redbeat entry name 用固定前缀, 与 schedule 的 python 调度区分
_REDBEAT_PREFIX = "cronflow:curl"


def _entry_name(curl_id: str) -> str:
    return f"{_REDBEAT_PREFIX}:{curl_id}"


def _sync_redbeat(curl: CurlTask) -> None:
    """根据 curl_task 配置同步 redbeat entry。"""
    try:
        from redbeat import RedBeatSchedulerEntry
        from worker.celery_app import celery_app

        name = _entry_name(curl.id)
        if not curl.is_enabled:
            # 删除
            try:
                entry = RedBeatSchedulerEntry.from_key(
                    f"redbeat:{name}", app=celery_app
                )
                entry.delete()
            except Exception:
                pass
            return

        from datetime import timedelta
        from celery.schedules import schedule as celery_schedule
        schedule = celery_schedule(timedelta(minutes=curl.minutes))
        entry = RedBeatSchedulerEntry(
            name=name,
            task="worker.run_curl_task",
            schedule=schedule,
            kwargs={
                "task_id": curl.id,
                "trigger_type": "interval",
            },
            app=celery_app,
        )
        entry.save()
    except Exception as e:
        print(f"[curl] redbeat sync failed for {curl.id}: {e}")


def _delete_redbeat(curl_id: str) -> None:
    try:
        from redbeat import RedBeatSchedulerEntry
        from worker.celery_app import celery_app
        name = _entry_name(curl_id)
        entry = RedBeatSchedulerEntry.from_key(f"redbeat:{name}", app=celery_app)
        entry.delete()
    except Exception:
        pass


def _notify() -> None:
    try:
        from app.core.eventbus_sync import emit_curl_changed
        emit_curl_changed()
    except Exception:
        pass


async def list_curl_tasks(db: AsyncSession) -> list[CurlTask]:
    rows = (await db.execute(select(CurlTask).order_by(CurlTask.created_at))).scalars().all()
    return list(rows)


async def create_curl_task(db: AsyncSession, payload: CurlTaskCreate) -> CurlTask:
    curl = CurlTask(
        id=uuid.uuid4().hex,
        name=payload.name,
        minutes=payload.minutes,
        is_enabled=payload.is_enabled,
        handler_type=payload.handler_type,
        target_collection=payload.target_collection,
        url=payload.request_config.url,
        method=payload.request_config.method,
        headers=payload.request_config.headers,
        data=payload.request_config.data,
    )
    db.add(curl)
    await db.commit()
    await db.refresh(curl)

    _sync_redbeat(curl)
    _notify()
    return curl


async def update_curl_task(db: AsyncSession, curl_id: str, payload: CurlTaskUpdate) -> CurlTask | None:
    curl = await db.get(CurlTask, curl_id)
    if not curl:
        return None
    if payload.name is not None:
        curl.name = payload.name
    if payload.minutes is not None:
        curl.minutes = payload.minutes
    if payload.is_enabled is not None:
        curl.is_enabled = payload.is_enabled
    if payload.handler_type is not None:
        curl.handler_type = payload.handler_type
    if payload.target_collection is not None:
        curl.target_collection = payload.target_collection
    if payload.request_config is not None:
        curl.url = payload.request_config.url
        curl.method = payload.request_config.method
        curl.headers = payload.request_config.headers
        curl.data = payload.request_config.data
    await db.commit()
    await db.refresh(curl)

    _sync_redbeat(curl)
    _notify()
    return curl


async def delete_curl_task(db: AsyncSession, curl_id: str) -> bool:
    curl = await db.get(CurlTask, curl_id)
    if not curl:
        return False
    _delete_redbeat(curl_id)
    await db.delete(curl)
    await db.commit()
    _notify()
    return True


async def trigger_curl_task(curl_id: str) -> str:
    """手动触发一次 cURL 同步。"""
    from worker.celery_app import celery_app
    result = celery_app.send_task(
        "worker.run_curl_task",
        kwargs={"task_id": curl_id, "trigger_type": "manual"},
    )
    return result.id
