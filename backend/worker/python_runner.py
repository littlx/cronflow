"""Celery 任务执行单元 — Python 注册函数。

职责:
1. 幂等校验 (Redis SET NX, 防同一触发被重复执行)
2. 写 running 日志 + stats 计数器
3. 执行注册函数 (按参数类型转换前端入参)
4. 写 success/failed 日志 + 更新计数器
5. emit new_log + stats_update
"""
from __future__ import annotations

import inspect
import time
import traceback
from datetime import datetime, timezone

from celery import shared_task

from app.core.config import settings
from app.core.db_sync import get_sync_session
from app.core.eventbus_sync import emit_new_log, emit_stats_update
from app.core.redis import sync_redis
from app.models.task_log import TaskLog
from app.registry import get_task
from app.registry.introspect import coerce_arg
from app.services.stats import mark_failed, mark_running, mark_success


def _idempotency_key(schedule_id: int | None, triggered_at: str | None) -> str | None:
    """幂等 key: schedule_id + 触发时刻。同一次触发不重复执行。"""
    if schedule_id is None or not triggered_at:
        return None
    return f"cronflow:idem:{schedule_id}:{triggered_at}"


def _acquire(key: str | None) -> bool:
    if not key:
        return True
    # SET NX EX 1天, 防重复
    return bool(sync_redis.set(key, "1", nx=True, ex=86400))


def _build_kwargs(func, task_args: dict) -> dict:
    """按函数签名过滤并转换入参。"""
    sig = inspect.signature(func)
    kwargs: dict = {}
    for name, param in sig.parameters.items():
        if name in task_args:
            kwargs[name] = coerce_arg(task_args[name], param.annotation)
        elif param.default is not inspect.Parameter.empty:
            kwargs[name] = param.default
    return kwargs


def _emit_stats() -> None:
    """执行完成后组装并推送 stats。worker 内用同步 session。"""
    try:
        import psutil
        from sqlalchemy import desc, select

        from app.models.schedule import JobSchedule
        from app.registry import TASKS

        session = get_sync_session()
        try:
            schedules = session.execute(select(JobSchedule)).scalars().all()
            active = [s for s in schedules if s.enabled]
            total_runs = int(sync_redis.get("cronflow:stats:total") or 0)
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
                "total_runs": total_runs,
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
        print(f"[python_runner] emit_stats failed: {e}")


@shared_task(
    bind=True,
    name="worker.run_python_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_max=settings.task_retry_max,
    time_limit=settings.task_time_limit,
    soft_time_limit=settings.task_soft_time_limit,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_python_task(self, task_id: str, trigger_type: str, task_args: dict | None = None,
                    schedule_id: int | None = None, triggered_at: str | None = None) -> dict:
    """执行一个注册的 Python 任务。

    幂等: 同一 (schedule_id, triggered_at) 只执行一次。手动触发 (triggered_at=None) 不去重。
    重试: 对未捕获异常自动指数退避重试, 最多 task_retry_max 次。最终失败写 failed 日志。
    """
    task_args = task_args or {}
    task_def = get_task(task_id)
    if not task_def:
        return {"ok": False, "error": f"task not found: {task_id}"}

    # 幂等
    key = _idempotency_key(schedule_id, triggered_at)
    if not _acquire(key):
        return {"ok": False, "skipped": True, "reason": "duplicate trigger"}

    func = task_def["func"]
    task_name = task_def["name"]

    # 写 running 日志
    session = get_sync_session()
    started = datetime.now(timezone.utc)
    log = TaskLog(
        task_id=task_id,
        task_name=task_name,
        trigger_type=trigger_type,
        schedule_id=schedule_id,
        status="running",
        started_at=started,
    )
    try:
        session.add(log)
        session.commit()
        session.refresh(log)
        log_id = log.id
    finally:
        session.close()

    mark_running()
    start_ts = time.time()

    try:
        kwargs = _build_kwargs(func, task_args)
        result = func(**kwargs) if kwargs else func()
        duration = time.time() - start_ts

        session = get_sync_session()
        try:
            log = session.get(TaskLog, log_id)
            log.status = "success"
            log.finished_at = datetime.now(timezone.utc)
            log.duration = round(duration, 3)
            log.result = str(result)[:8000]
            session.commit()
            log_dict = log.to_dict()
        finally:
            session.close()

        mark_success()
        emit_new_log(log_dict)
        _emit_stats()
        return {"ok": True, "log_id": log_id}

    except Exception:
        duration = time.time() - start_ts
        err = traceback.format_exc()
        # 重试尚未耗尽: 不写 failed, 让 celery 重试 (但更新 running->failed 计数会在最终失败时)
        if self.request.retries < settings.task_retry_max:
            # 仍标记本次为失败日志, 便于观察; 重试会创建新日志
            session = get_sync_session()
            try:
                log = session.get(TaskLog, log_id)
                log.status = "failed"
                log.finished_at = datetime.now(timezone.utc)
                log.duration = round(duration, 3)
                log.error = f"[retry {self.request.retries + 1}] {err}"[:8000]
                session.commit()
                log_dict = log.to_dict()
            finally:
                session.close()
            mark_failed()
            emit_new_log(log_dict)
            raise  # 触发 celery 重试
        else:
            # 重试耗尽: 最终失败
            session = get_sync_session()
            try:
                log = session.get(TaskLog, log_id)
                log.status = "failed"
                log.finished_at = datetime.now(timezone.utc)
                log.duration = round(duration, 3)
                log.error = err[:8000]
                session.commit()
                log_dict = log.to_dict()
            finally:
                session.close()
            mark_failed()
            emit_new_log(log_dict)
            _emit_stats()
            return {"ok": False, "log_id": log_id, "error": "max retries exceeded"}
