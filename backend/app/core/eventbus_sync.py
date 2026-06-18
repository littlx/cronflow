"""EventBus 同步 emit helper — 供 Celery worker 进程使用。

用同步 RedisManager 作为 client_manager, emit 经 Redis 扇出到持有前端连接的 API 进程。
单例缓存, 根治 fd 泄漏。
"""
from __future__ import annotations

import socketio
from socketio import RedisManager, Server

from app.core.config import settings
from app.core.eventbus import (
    EVENT_NEW_LOG,
    EVENT_STATS_UPDATE,
    EVENT_SCHEDULE_CHANGED,
    EVENT_CURL_CHANGED,
)

_sync_manager: RedisManager | None = None
_sync_sio: Server | None = None


def _get_sync_sio() -> Server:
    global _sync_manager, _sync_sio
    if _sync_sio is None:
        _sync_manager = RedisManager(settings.redis_url)
        _sync_sio = Server(
            async_mode="threading",
            client_manager=_sync_manager,
            logger=False,
            engineio_logger=False,
        )
    return _sync_sio


def emit_sync(event: str, data: dict) -> None:
    """worker 进程同步 emit, 经 Redis 扇出到 API 进程的前端连接。"""
    try:
        _get_sync_sio().emit(event, data)
    except Exception as e:
        print(f"[eventbus-sync] emit {event} failed: {e}")


def emit_new_log(log_dict: dict) -> None:
    emit_sync(EVENT_NEW_LOG, log_dict)


def emit_stats_update(stats: dict) -> None:
    emit_sync(EVENT_STATS_UPDATE, stats)


def emit_schedule_changed() -> None:
    emit_sync(EVENT_SCHEDULE_CHANGED, {})


def emit_curl_changed() -> None:
    emit_sync(EVENT_CURL_CHANGED, {})
