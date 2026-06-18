"""统一 Celery 执行单元 — worker.run_task。

唯一入口: 解析 task_ref → kind → 分派到对应 handler。
共享逻辑: 幂等 / 写日志 / 重试 / Redis 计数器 / emit。

handler 只关心"做什么", runner 关心"怎么跑、记录、广播"。
"""
from __future__ import annotations

import time
import traceback
from datetime import datetime, timezone
from typing import Any

from celery import shared_task

from app.core.config import settings
from app.core.db_sync import get_sync_session
from app.core.eventbus_sync import emit_curl_changed, emit_new_log, emit_stats_update
from app.core.redis import sync_redis
from app.models.task_log import TaskLog
from app.services.ref_resolver import resolve_ref_sync
from app.services.stats import mark_failed, mark_running, mark_success
from worker.handlers import HandlerResult, curl_handler, python_handler

# kind -> handler module
_HANDLERS = {
    python_handler.kind: python_handler,
    curl_handler.kind: curl_handler,
}


def _idempotency_key(schedule_id: int | None, triggered_at: str | None) -> str | None:
    if schedule_id is None or not triggered_at:
        return None
    return f"cronflow:idem:{schedule_id}:{triggered_at}"


def _acquire(key: str | None) -> bool:
    if not key:
        return True
    return bool(sync_redis.set(key, "1", nx=True, ex=86400))


def _emit_stats() -> None:
    try:
        import psutil
        from sqlalchemy import desc, select

        from app.models.schedule import JobSchedule
        from app.registry import TASKS

        session = get_sync_session()
        try:
            schedules = session.execute(select(JobSchedule)).scalars().all()
            active = [s for s in schedules if s.enabled]
            total = int(sync_redis.get("cronflow:stats:total") or 0)
            success = int(sync_redis.get("cronflow:stats:success") or 0)
            failed = int(sync_redis.get("cronflow:stats:failed") or 0)
            running = int(sync_redis.get("cronflow:stats:running") or 0)
            finished = success + failed
            rate = round((success / finished) * 100, 2) if finished > 0 else 0.0
            recent = session.execute(
                select(TaskLog).order_by(desc(TaskLog.started_at)).limit(10)
            ).scalars().all()
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            payload = {
                "total_tasks": len(TASKS),
                "total_schedules": len(schedules),
                "active_schedules": len(active),
                "total_runs": total,
                "success_runs": success,
                "failed_runs": failed,
                "running_runs": running,
                "success_rate": rate,
                "system": {"cpu_usage": cpu, "memory_usage": mem},
                "recent_logs": [r.to_dict() for r in recent],
            }
        finally:
            session.close()
        emit_stats_update(payload)
    except Exception as e:
        print(f"[task_runner] emit_stats failed: {e}")


@shared_task(
    bind=True,
    name="worker.run_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_max=settings.task_retry_max,
    time_limit=settings.task_time_limit,
    soft_time_limit=settings.task_soft_time_limit,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_task(
    self,
    task_ref: str,
    trigger_type: str = "manual",
    task_args: dict[str, Any] | None = None,
    schedule_id: int | None = None,
    triggered_at: str | None = None,
) -> dict:
    """统一任务执行入口。"""
    task_args = task_args or {}

    # 幂等
    idem = _idempotency_key(schedule_id, triggered_at)
    if not _acquire(idem):
        return {"ok": False, "skipped": True, "reason": "duplicate trigger"}

    # 1) 解析 ref → resolved task
    session = get_sync_session()
    try:
        resolved = resolve_ref_sync(session, task_ref)
        if not resolved:
            return {"ok": False, "error": f"task ref not found: {task_ref}"}

        handler = _HANDLERS.get(resolved.kind)
        if not handler:
            return {"ok": False, "error": f"no handler for kind={resolved.kind}"}

        # 2) 写 running 日志
        started = datetime.now(timezone.utc)
        log = TaskLog(
            task_id=resolved.ref,
            task_name=resolved.name,
            trigger_type=trigger_type,
            schedule_id=schedule_id,
            status="running",
            started_at=started,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        log_id = log.id
    finally:
        session.close()

    mark_running()
    start_ts = time.time()

    try:
        # 3) 执行 handler (新开 session, 让 handler 读 task 配置或写 cache)
        session = get_sync_session()
        try:
            resolved = resolve_ref_sync(session, task_ref) or resolved
            result: HandlerResult = handler.execute(session, resolved, task_args)
            session.commit()  # handler 内部可能 add 缓存等, 在此提交
        finally:
            session.close()

        duration = time.time() - start_ts

        # 4) 写 success 日志
        session = get_sync_session()
        try:
            log = session.get(TaskLog, log_id)
            log.status = "success"
            log.finished_at = datetime.now(timezone.utc)
            log.duration = round(duration, 3)
            log.result = result.result_text
            session.commit()
            log_dict = log.to_dict()
        finally:
            session.close()

        mark_success()
        emit_new_log(log_dict)
        if resolved.kind == "curl":
            emit_curl_changed()
        _emit_stats()
        return {"ok": True, "log_id": log_id, "kind": resolved.kind}

    except Exception:
        duration = time.time() - start_ts
        err = traceback.format_exc()
        is_final = self.request.retries >= settings.task_retry_max

        session = get_sync_session()
        try:
            log = session.get(TaskLog, log_id)
            if log:
                log.status = "failed"
                log.finished_at = datetime.now(timezone.utc)
                log.duration = round(duration, 3)
                log.error = (err if is_final else f"[retry {self.request.retries+1}] {err}")[:8000]
                session.commit()
                log_dict = log.to_dict()
            else:
                log_dict = {}
        finally:
            session.close()

        mark_failed()
        emit_new_log(log_dict)

        if not is_final:
            raise  # celery 自动退避重试
        _emit_stats()
        return {"ok": False, "log_id": log_id, "error": "max retries exceeded"}
