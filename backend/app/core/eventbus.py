"""EventBus — 唯一的 SocketIO emit 出口。

单进程架构: 用 AsyncServer 默认内存 manager, 不再需要 Redis 跨进程扇出。
根治旧版 fd 泄漏: 全局单例, 整个进程一份。

main.py 把 sio 用 socketio.ASGIApp 包在 FastAPI 外层 (FastAPI 作为
other_asgi_app), 这样 /socket.io 路径走 sio, 其他请求走 FastAPI。
"""
from __future__ import annotations

from socketio import AsyncServer

from app.core.logging import get_logger

logger = get_logger("eventbus")

# 单进程: 内存 manager, 无需 Redis
sio: AsyncServer = AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# ---- 事件名常量, 前后端共用 ----
EVENT_NEW_LOG = "new_log"
EVENT_STATS_UPDATE = "stats_update"
EVENT_SCHEDULE_CHANGED = "schedule_changed"
EVENT_CURL_CHANGED = "curl_changed"


@sio.event
async def connect(sid, environ):  # noqa: ANN001
    logger.info("client connected", sid=sid)


@sio.event
async def disconnect(sid):  # noqa: ANN001
    logger.info("client disconnected", sid=sid)


async def emit(event: str, data: dict) -> None:
    """进程内 async emit (单进程直接扇出给前端连接)。"""
    try:
        await sio.emit(event, data)
    except Exception:
        logger.exception("emit failed", event=event)
