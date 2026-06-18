"""统一 Celery 执行单元 — worker.run_task。

唯一入口: 解析 task_ref → kind → 分派到对应 handler。
共享逻辑: 幂等 / 写日志 / 重试 / Redis 计数器 / emit。

handler 只关心"做什么", runner 关心"怎么跑、记录、广播"。

执行语义 (与重试):
- 首次进入 (retries==0): 计算/接收 triggered_at, 抢幂等锁; 失败即跳过。
- 每次 attempt 都新建一行 TaskLog (attempt 字段 = retries+1), 重试历史完整可追溯。
- Redis 计数器: 首次进入 mark_running (running++, total++); 终态 (成功/最终失败)
  统一 mark_success / mark_failed (running--, success/failed++). 重试中间态不计数。
- _emit_stats 仅在终态广播, 避免被重试压垮。
"""
from __future__ import annotations

import time
import traceback
from datetime import datetime, timezone
from typing import Any

import httpx
from celery import shared_task
from sqlalchemy.exc import OperationalError

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

# 只对真正的"瞬态"故障自动重试; 业务错误 (KeyError / RuntimeError / 4xx 等) 终态失败,
# 避免无意义的浪费与日志爆炸。
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.RequestError,         # 含 TimeoutException / ConnectError / NetworkError 等
    httpx.HTTPStatusError,      # 5xx 视为瞬态; 4xx 由 curl_handler 自行 raise_for_status 时一并算入
    ConnectionError,
    TimeoutError,
    OperationalError,           # PG 连接抖动 / 锁等待超时等瞬态故障
)


def _idempotency_key(schedule_id: int | None, triggered_at: str | None) -> str | None:
    if schedule_id is None or not triggered_at:
        return None
    return f"cronflow:idem:{schedule_id}:{triggered_at}"


def _acquire(key: str | None) -> bool:
    if not key:
        return True
    return bool(sync_redis.set(key, "1", nx=True, ex=86400))


def _auto_triggered_at() -> str:
    """beat 未注入 triggered_at 时的兜底: 用 UTC 秒级戳作为同一次触发的唯一 ID。
    redbeat 已做 leader election, 重复 send_task 仅可能发生在毫秒级抖动窗口,
    秒级精度足够 dedupe。"""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


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
    autoretry_for=_RETRYABLE_EXCEPTIONS,
    retry_backoff=True,
    max_retries=settings.task_retry_max,
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
    attempt = self.request.retries + 1
    is_first_attempt = self.request.retries == 0

    # ---- 幂等 (首次进入才检查; 重试已经持锁, 必须放行)
    if is_first_attempt:
        if schedule_id is not None and not triggered_at:
            triggered_at = _auto_triggered_at()
        idem = _idempotency_key(schedule_id, triggered_at)
        if not _acquire(idem):
            return {"ok": False, "skipped": True, "reason": "duplicate trigger"}

    # ---- 1) 解析 ref → resolved task
    session = get_sync_session()
    try:
        resolved = resolve_ref_sync(session, task_ref)
        if not resolved:
            return {"ok": False, "error": f"task ref not found: {task_ref}"}

        handler = _HANDLERS.get(resolved.kind)
        if not handler:
            return {"ok": False, "error": f"no handler for kind={resolved.kind}"}

        # ---- 2) 写一行 running 日志 (每次 attempt 都新建, 不再覆盖)
        started = datetime.now(timezone.utc)
        log = TaskLog(
            task_id=resolved.ref,
            task_name=resolved.name,
            trigger_type=trigger_type,
            schedule_id=schedule_id,
            status="running",
            started_at=started,
            attempt=attempt,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        log_id = log.id
    finally:
        session.close()

    # 计数器: 首次进入累加; 重试中间态不动 (避免重复)
    if is_first_attempt:
        mark_running()
    start_ts = time.time()

    try:
        # ---- 3) 执行 handler
        session = get_sync_session()
        try:
            resolved = resolve_ref_sync(session, task_ref) or resolved
            result: HandlerResult = handler.execute(session, resolved, task_args)
            session.commit()
        finally:
            session.close()

        duration = time.time() - start_ts

        # ---- 4) 写 success 日志
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

        # 终态: 扣 running, 增 success, 广播
        mark_success()
        emit_new_log(log_dict)
        if resolved.kind == "curl":
            emit_curl_changed()
        _emit_stats()
        return {"ok": True, "log_id": log_id, "kind": resolved.kind, "attempt": attempt}

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
                log.error = err[:8000]
                session.commit()
                log_dict = log.to_dict()
            else:
                log_dict = {}
        finally:
            session.close()

        # 每次失败的日志行都广播, 让前端看到重试过程
        emit_new_log(log_dict)

        if not is_final:
            # 中间态: 不动计数器, 让 celery 自动退避重试
            # (本 attempt 的 log 已写入 failed, 下次 attempt 会新开一行)
            raise

        # 终态失败: 扣 running, 增 failed, 推送统计
        mark_failed()
        _emit_stats()
        return {
            "ok": False, "log_id": log_id,
            "error": "max retries exceeded", "attempt": attempt,
        }
