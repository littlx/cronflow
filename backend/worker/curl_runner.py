"""Celery 任务执行单元 — cURL/API 数据同步。

职责:
1. 从 DB 取 curl_task 配置
2. httpx 发起请求
3. 按 handler_type 处理响应, 写入 crawled_data_cache (JSONB)
4. 更新 curl_task 执行状态
5. 写 task_logs + emit
"""
from __future__ import annotations

import time
import traceback
from datetime import datetime, timezone

import httpx
from celery import shared_task

from app.core.config import settings
from app.core.db_sync import get_sync_session
from app.core.eventbus_sync import emit_new_log, emit_stats_update, emit_curl_changed
from app.models.cache import CrawledDataCache
from app.models.curl_task import CurlTask
from app.models.task_log import TaskLog
from app.services.stats import mark_failed, mark_running, mark_success


def _process_response(handler_type: str, status_code: int, body):
    """按 handler_type 抽取要缓存的数据。"""
    if handler_type == "RAW_RESPONSE":
        return {"_raw": body if isinstance(body, str) else str(body), "_status": status_code}
    # 尝试 JSON 解析
    if isinstance(body, (dict, list)):
        if handler_type == "NESTED_DATA" and isinstance(body, dict):
            # 取常见的 data 字段
            for key in ("data", "result", "items", "list", "results"):
                if key in body and isinstance(body[key], (list, dict)):
                    return body[key]
            return body
        return body
    # 非结构化文本, 包装一层
    return {"_text": str(body)[:8000], "_status": status_code}


@shared_task(
    bind=True,
    name="worker.run_curl_task",
    autoretry_for=(httpx.RequestError, httpx.HTTPStatusError),
    retry_backoff=True,
    retry_max=settings.task_retry_max,
    time_limit=settings.task_time_limit,
    soft_time_limit=settings.task_soft_time_limit,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_curl_task(self, task_id: str, trigger_type: str = "interval",
                  schedule_id: int | None = None, triggered_at: str | None = None) -> dict:
    """执行一个 cURL 数据同步任务。"""
    session = get_sync_session()
    try:
        curl = session.get(CurlTask, task_id)
        if not curl:
            return {"ok": False, "error": f"curl task not found: {task_id}"}

        curl.status = "running"
        session.commit()

        started = datetime.now(timezone.utc)
        log = TaskLog(
            task_id=task_id,
            task_name=curl.name,
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
        # 重新取一份配置 (避免 session 跨请求持有)
        session = get_sync_session()
        curl = session.get(CurlTask, task_id)
        method = (curl.method or "GET").upper()
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(
                method=method,
                url=curl.url,
                headers=curl.headers or {},
                json=curl.data if (curl.data and method != "GET") else None,
            )
            resp.raise_for_status()
            try:
                body = resp.json()
            except Exception:
                body = resp.text

        document = _process_response(curl.handler_type, resp.status_code, body)
        duration = time.time() - start_ts

        # 写缓存
        cache = CrawledDataCache(
            target_collection=curl.target_collection,
            document=document,
        )
        session.add(cache)

        # 更新 curl_task 状态
        now = datetime.now(timezone.utc)
        curl.status = "idle"
        curl.last_run_time = now
        curl.last_run_result = "success"
        curl.error_message = None

        # 日志
        log = session.get(TaskLog, log_id)
        log.status = "success"
        log.finished_at = now
        log.duration = round(duration, 3)
        log.result = f"cached to {curl.target_collection} (http {resp.status_code})"
        session.commit()
        session.refresh(log)
        log_dict = log.to_dict()
        session.close()

        mark_success()
        emit_new_log(log_dict)
        emit_curl_changed()
        _emit_stats_local()
        return {"ok": True, "log_id": log_id}

    except Exception:
        duration = time.time() - start_ts
        err = traceback.format_exc()
        if self.request.retries < settings.task_retry_max:
            session = get_sync_session()
            try:
                curl = session.get(CurlTask, task_id)
                if curl:
                    curl.status = "error"
                    curl.last_run_result = "fail"
                    curl.error_message = err[:2000]
                log = session.get(TaskLog, log_id)
                if log:
                    log.status = "failed"
                    log.finished_at = datetime.now(timezone.utc)
                    log.duration = round(duration, 3)
                    log.error = f"[retry {self.request.retries+1}] {err}"[:8000]
                session.commit()
            finally:
                session.close()
            mark_failed()
            raise
        else:
            session = get_sync_session()
            try:
                curl = session.get(CurlTask, task_id)
                if curl:
                    curl.status = "error"
                    curl.last_run_result = "fail"
                    curl.last_run_time = datetime.now(timezone.utc)
                    curl.error_message = err[:2000]
                log = session.get(TaskLog, log_id)
                if log:
                    log.status = "failed"
                    log.finished_at = datetime.now(timezone.utc)
                    log.duration = round(duration, 3)
                    log.error = err[:8000]
                session.commit()
                session.refresh(log) if log else None
                log_dict = log.to_dict() if log else {}
            finally:
                session.close()
            mark_failed()
            emit_new_log(log_dict)
            return {"ok": False, "log_id": log_id, "error": "max retries exceeded"}


def _emit_stats_local() -> None:
    """复用 python_runner 的 stats 推送逻辑。"""
    try:
        from worker.python_runner import _emit_stats
        _emit_stats()
    except Exception:
        pass
