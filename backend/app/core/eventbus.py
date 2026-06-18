"""EventBus — 唯一的 SocketIO emit 出口。

设计目标: 收敛所有实时推送到一个单例, 根治 fd 泄漏。
架构:
- API 主进程: AsyncServer(async_mode='asgi') 持有前端 websocket 连接, 同时用 AsyncRedisManager
  作为 client_manager, 订阅 Redis 上的扇出消息。
- Worker 进程: 通过同步 RedisManager.emit() 把消息发到 Redis, 由 API 进程的 AsyncRedisManager
  订阅后扇出给所有连接的前端 client。

关键: 两端必须使用同一个 Redis manager (相同 redis url + channel), 才能跨进程扇出。
"""
from __future__ import annotations

import socketio
from socketio import AsyncRedisManager, AsyncServer, RedisManager, Server

from app.core.config import settings

# 共享的 Redis manager: API 端用 async, worker 端用 sync, 但都连同一个 Redis,
# socketio 内部用相同的 channel ('socketio') 扇出。
_redis_url = settings.redis_url

# API 端: async server, 持有前端连接 + 订阅 Redis 扇出
_async_manager = AsyncRedisManager(_redis_url)
sio: AsyncServer = AsyncServer(
    async_mode="asgi",
    client_manager=_async_manager,
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# 可被 FastAPI 挂载的 ASGI app
sio_app = socketio.ASGIApp(sio, socketio_path="socket.io")

# ---- 事件名常量, 前后端共用 ----
EVENT_NEW_LOG = "new_log"
EVENT_STATS_UPDATE = "stats_update"
EVENT_SCHEDULE_CHANGED = "schedule_changed"
EVENT_CURL_CHANGED = "curl_changed"


@sio.event
async def connect(sid, environ):  # noqa: ANN001
    print(f"[EventBus] client connected: {sid}")


@sio.event
async def disconnect(sid):  # noqa: ANN001
    print(f"[EventBus] client disconnected: {sid}")


async def emit(event: str, data: dict) -> None:
    """API 进程内 async emit (经 Redis manager 扇出)。"""
    await sio.emit(event, data)
