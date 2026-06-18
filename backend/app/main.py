"""CronFlow v2 FastAPI 入口。

挂载:
- REST API 路由 (/api/*)
- SocketIO ASGI app (/socket.io)
- Prometheus metrics (/metrics) — 阶段6接入
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.eventbus import sio_app
from app.core.logging import setup_logging
from app.routers import health, tasks, logs, stats, schedules, curl, metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # 启动: 触发任务发现 (注册 @register_task 的函数)
    from app.registry.discover import discover_tasks

    discover_tasks()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST 路由
    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(logs.router)
    app.include_router(stats.router)
    app.include_router(schedules.router)
    app.include_router(curl.router)
    app.include_router(metrics.router)

    # SocketIO 挂载到根路径, 与 FastAPI 共享 ASGI
    app.mount("/", sio_app)

    return app


app = create_app()
