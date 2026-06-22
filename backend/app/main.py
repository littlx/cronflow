"""CronFlow FastAPI 入口。

单进程架构: API + scheduler + executor + eventbus 全在一个进程。
lifespan 启动顺序:
1. setup_logging
2. discover_tasks (注册 @register_task 函数)
3. reconcile_running_logs (修复崩溃残留的 running 状态)
4. init_executor (创建协程池单例)
5. scheduler_loop (asyncio task, 后台调度)

挂载:
- REST API 路由 (/api/*)
- SocketIO ASGI app (/socket.io)
- Prometheus metrics (/metrics)
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.eventbus import sio_app
from app.core.logging import get_logger, setup_logging
from app.routers import cache, health, logs, metrics, schedules, stats, tasks
from app.services.scheduler import scheduler_loop

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("starting cronflow", app=settings.app_name)

    # 1. 触发任务发现 (注册 @register_task 的函数)
    from app.registry.discover import discover_tasks
    discover_tasks()

    # 2. 启动 reconciliation: 修复崩溃残留的 running 状态
    from app.services.stats import reconcile_running_logs
    async with AsyncSessionLocal() as db:
        fixed = await reconcile_running_logs(db)
        if fixed:
            logger.info("reconciled running logs", fixed=fixed)

    # 3. 初始化 executor (协程池单例)
    from app.services.executor import init_executor
    init_executor(max_concurrency=settings.max_concurrency)

    # 4. 启动调度循环 (后台 asyncio task)
    scheduler_task = asyncio.create_task(scheduler_loop())

    logger.info("cronflow ready")
    yield

    # 关闭: 取消调度循环
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    logger.info("cronflow stopped")


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
    app.include_router(cache.router)
    app.include_router(metrics.router)

    # SocketIO 挂载到根路径, 与 FastAPI 共享 ASGI
    app.mount("/", sio_app)

    return app


app = create_app()
