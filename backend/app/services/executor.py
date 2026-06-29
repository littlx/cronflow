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
from app.core.metrics import TASK_DURATION, TASK_TOTAL
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
        """执行一个任务。在信号量外写入 pending 状态，并在 Semaphore 限制内运行。"""
        # 1. 首次进入抢幂等锁
        if schedule_id is not None:
            if not triggered_at:
                triggered_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            if not await self._acquire_idempotency(schedule_id, triggered_at):
                return {"ok": False, "skipped": True, "reason": "duplicate trigger"}

        # 2. 持久化排队 (pending) 状态日志，防止队列积压期间进程崩溃丢失记录
        log_id, started = await self._write_log_state(
            task_ref, trigger_type, schedule_id, attempt=1, status="pending"
        )
        if log_id is None:
            return {"ok": False, "error": "task ref not found or no handler"}

        # 发送 pending 日志给前端展示
        await self._emit_log(await self._get_log_dict(log_id))
        await self._emit_stats()

        # 3. 进入协程池排队
        async with self._sem:
            return await self._run_with_retry(
                log_id, task_ref, trigger_type, task_args or {}, schedule_id, triggered_at
            )

    async def _run_with_retry(
        self,
        first_log_id: int,
        task_ref: str,
        trigger_type: str,
        task_args: dict[str, Any],
        schedule_id: int | None,
        triggered_at: str | None,
    ) -> dict:
        """含重试逻辑的执行。首次尝试更新 pending 日志，重试尝试新建日志。"""
        attempt = 0
        last_error: Exception | None = None
        log_id = first_log_id

        while attempt <= settings.task_retry_max:
            attempt += 1
            if attempt == 1:
                # 首次执行：将已存在的 pending 日志更新为 running 并校正开始时间
                await self._update_log_status(log_id, "running")
            else:
                # 重试执行：新建运行日志，完整追溯重试历史
                log_id, _ = await self._write_log_state(
                    task_ref, trigger_type, schedule_id, attempt, status="running"
                )
                if log_id is None:
                    return {"ok": False, "error": "task ref not found or no handler"}

            # 发送 running 状态推送
            log_dict = await self._get_log_dict(log_id)
            await self._emit_log(log_dict)
            await self._emit_stats()

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
                self._record_metric(task_ref, "success", trigger_type, duration)
                await self._notify("task_success", log_dict, task_ref)
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
                    self._record_metric(task_ref, "failed", trigger_type, duration)
                    await self._notify("task_failed", log_dict, task_ref)
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
                await self._notify("task_failed", log_dict, task_ref)
                self._record_metric(task_ref, "failed", trigger_type, duration)
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

    async def _write_log_state(
        self, task_ref: str, trigger_type: str, schedule_id: int | None, attempt: int, status: str
    ) -> tuple[int | None, datetime]:
        """写一行指定状态的日志, 返回 (log_id, started_at)。"""
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
                status=status,
                started_at=started,
                attempt=attempt,
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
            return log.id, started

    async def _update_log_status(self, log_id: int, status: str) -> None:
        """更新日志状态并校准其开始时间。"""
        async with AsyncSessionLocal() as session:
            log = await session.get(TaskLog, log_id)
            if log:
                log.status = status
                log.started_at = datetime.now(timezone.utc)
                await session.commit()

    async def _get_log_dict(self, log_id: int) -> dict:
        """获取日志的 dict。"""
        async with AsyncSessionLocal() as session:
            log = await session.get(TaskLog, log_id)
            return log.to_dict() if log else {}

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

    async def _notify(self, event: str, log_dict: dict, task_ref: str) -> None:
        """终态时触发通知派发 (失败/成功都走这里, 由通知配置的 events 决定是否发)。"""
        try:
            from app.notifiers import notify_event
            await notify_event(event, {"log": log_dict, "task_ref": task_ref})
        except Exception:
            logger.exception("notify failed")

    @staticmethod
    def _record_metric(task_ref: str, status: str, trigger_type: str, duration: float) -> None:
        """终态时记一笔 prometheus 指标 (counter + histogram)。失败绝不影响主路径。"""
        try:
            TASK_TOTAL.labels(task_ref=task_ref, status=status, trigger_type=trigger_type).inc()
            TASK_DURATION.labels(task_ref=task_ref).observe(duration)
        except Exception:
            pass


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
