"""统一任务执行器 — 替代旧版 celery task_runner。

单进程 asyncio 协程池, Semaphore 限并发。
共享逻辑: 幂等 / 写日志 / 重试 / emit / 通知 / prometheus。

执行语义 (与重试):
- 首次进入: 抢幂等锁 (idempotency_keys 表 INSERT ON CONFLICT); 失败即跳过。
- 每次 attempt 都新建一行 TaskLog (attempt 字段 = 当前次数), 重试历史完整可追溯。
- 重试只对"瞬态"故障 (网络错误/5xx/DB 抖动); 业务错误 (RuntimeError/4xx) 终态失败。
- 终态 (成功/最终失败) 时触发通知器 (失败时) + emit。
"""
from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import insert, select
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.eventbus import EVENT_CURL_CHANGED, EVENT_NEW_LOG, EVENT_STATS_UPDATE, emit
from app.core.logging import get_logger
from app.handlers import get_handler
from app.models.idempotency import IdempotencyKey
from app.models.task_log import TaskLog
from app.services.ref_resolver import resolve_ref
from app.services.stats import compute_stats

logger = get_logger("executor")

# 只对真正的"瞬态"故障自动重试; 业务错误 (RuntimeError / 4xx 等) 终态失败,
# 避免无意义的浪费与日志爆炸。
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.RequestError,         # 含 TimeoutException / ConnectError / NetworkError 等
    httpx.HTTPStatusError,      # 5xx (curl handler 已过滤 4xx, 这里只会是 5xx)
    ConnectionError,
    TimeoutError,
    OperationalError,           # DB 连接抖动等瞬态故障
)


class Executor:
    """统一任务执行入口。单例, lifespan 时创建。"""

    def __init__(self, max_concurrency: int = 8):
        self._sem = asyncio.Semaphore(max_concurrency)

    async def run(
        self,
        task_ref: str,
        trigger_type: str = "manual",
        task_args: dict[str, Any] | None = None,
        schedule_id: int | None = None,
        triggered_at: str | None = None,
    ) -> dict:
        """执行一个任务。非阻塞投递 (经 Semaphore 排队)。"""
        async with self._sem:
            return await self._run_with_retry(
                task_ref, trigger_type, task_args or {}, schedule_id, triggered_at
            )

    async def _run_with_retry(
        self,
        task_ref: str,
        trigger_type: str,
        task_args: dict[str, Any],
        schedule_id: int | None,
        triggered_at: str | None,
    ) -> dict:
        """含重试逻辑的执行。每次 attempt 新建一行日志。"""
        # 首次进入才抢幂等锁; 重试已经持锁, 必须放行
        is_first_attempt = True
        if schedule_id is not None:
            if not triggered_at:
                triggered_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            if is_first_attempt and not await self._acquire_idempotency(schedule_id, triggered_at):
                return {"ok": False, "skipped": True, "reason": "duplicate trigger"}

        attempt = 0
        last_error: Exception | None = None

        while attempt <= settings.task_retry_max:
            attempt += 1
            log_id, started = await self._write_running_log(
                task_ref, trigger_type, schedule_id, attempt
            )
            if log_id is None:
                return {"ok": False, "error": "task ref not found or no handler"}

            start_ts = time.time()
            try:
                async with AsyncSessionLocal() as session:
                    resolved = await resolve_ref(session, task_ref)
                    if not resolved:
                        raise RuntimeError(f"task ref not found: {task_ref}")
                    handler = get_handler(resolved.kind)
                    if not handler:
                        raise RuntimeError(f"no handler for kind={resolved.kind}")

                    result = await handler.execute(session, resolved, task_args)
                    await session.commit()

                duration = time.time() - start_ts
                log_dict = await self._finalize_log(
                    log_id, "success", duration, result.result_text, None
                )
                await self._emit_log(log_dict)
                await self._emit_stats()
                if resolved.kind == "curl":
                    await emit(EVENT_CURL_CHANGED, {})
                logger.info(
                    "task succeeded", task_ref=task_ref, attempt=attempt, duration=round(duration, 3)
                )
                return {"ok": True, "log_id": log_id, "attempt": attempt}

            except _RETRYABLE_EXCEPTIONS as e:
                duration = time.time() - start_ts
                last_error = e
                is_final = attempt > settings.task_retry_max
                log_dict = await self._finalize_log(
                    log_id, "failed", duration, None, traceback.format_exc()[:8000]
                )
                await self._emit_log(log_dict)

                if is_final:
                    logger.warning(
                        "task failed (max retries)", task_ref=task_ref,
                        attempt=attempt, error=str(e),
                    )
                    await self._emit_stats()
                    # 终态失败: 触发通知
                    await self._notify_failure(log_dict)
                    return {
                        "ok": False, "log_id": log_id,
                        "error": "max retries exceeded", "attempt": attempt,
                    }
                # 退避后重试
                backoff = settings.task_retry_backoff * (2 ** (attempt - 1))
                logger.info(
                    "task retrying", task_ref=task_ref, attempt=attempt,
                    backoff=backoff, error=str(e),
                )
                await asyncio.sleep(backoff)

            except Exception as e:
                # 业务错误 (RuntimeError / 4xx 等): 终态失败, 不重试
                duration = time.time() - start_ts
                log_dict = await self._finalize_log(
                    log_id, "failed", duration, None, traceback.format_exc()[:8000]
                )
                await self._emit_log(log_dict)
                await self._emit_stats()
                logger.warning(
                    "task failed (business error)", task_ref=task_ref,
                    attempt=attempt, error=str(e),
                )
                await self._notify_failure(log_dict)
                return {
                    "ok": False, "log_id": log_id,
                    "error": str(e), "attempt": attempt,
                }

        # 理论上不会走到这里
        return {"ok": False, "error": str(last_error), "attempt": attempt}

    async def _acquire_idempotency(self, schedule_id: int, triggered_at: str) -> bool:
        """幂等锁: INSERT idempotency_keys, 唯一约束冲突 = 重复, 返回 False。"""
        key = f"cronflow:idem:{schedule_id}:{triggered_at}"
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    insert(IdempotencyKey).values(key=key, schedule_id=schedule_id)
                )
                await session.commit()
                return True
        except Exception:
            # 唯一约束冲突或其他异常, 视为重复
            return False

    async def _write_running_log(
        self, task_ref: str, trigger_type: str, schedule_id: int | None, attempt: int
    ) -> tuple[int | None, datetime]:
        """写一行 running 日志, 返回 (log_id, started_at)。"""
        started = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            resolved = await resolve_ref(session, task_ref)
            if not resolved:
                return None, started
            handler = get_handler(resolved.kind)
            if not handler:
                return None, started

            log = TaskLog(
                task_ref=resolved.ref,
                task_name=resolved.name,
                trigger_type=trigger_type,
                schedule_id=schedule_id,
                status="running",
                started_at=started,
                attempt=attempt,
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
            return log.id, started

    async def _finalize_log(
        self,
        log_id: int,
        status: str,
        duration: float,
        result_text: str | None,
        error: str | None,
    ) -> dict:
        """更新日志为终态, 返回 log_dict 供 emit。"""
        async with AsyncSessionLocal() as session:
            log = await session.get(TaskLog, log_id)
            if not log:
                return {}
            log.status = status
            log.finished_at = datetime.now(timezone.utc)
            log.duration = round(duration, 3)
            log.result = result_text
            log.error = error
            await session.commit()
            await session.refresh(log)
            return log.to_dict()

    async def _emit_log(self, log_dict: dict) -> None:
        if log_dict:
            await emit(EVENT_NEW_LOG, log_dict)

    async def _emit_stats(self) -> None:
        try:
            async with AsyncSessionLocal() as session:
                payload = await compute_stats(session)
            await emit(EVENT_STATS_UPDATE, payload)
        except Exception:
            logger.exception("emit_stats failed")

    async def _notify_failure(self, log_dict: dict) -> None:
        """终态失败时触发通知器。首版 notifier 为空实现, 阶段3接入。"""
        try:
            from app.notifiers import notify_event
            await notify_event("task_failed", {"log": log_dict})
        except Exception:
            logger.exception("notify failed")


# 全局单例, lifespan 时初始化
executor: Executor | None = None


def get_executor() -> Executor:
    if executor is None:
        raise RuntimeError("Executor not initialized")
    return executor


def init_executor(max_concurrency: int = 8) -> Executor:
    global executor
    executor = Executor(max_concurrency=max_concurrency)
    return executor
