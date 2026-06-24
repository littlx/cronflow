"""CronFlow FastAPI 入口。

单进程架构: API + scheduler + executor + eventbus 全在一个进程。
lifespan 启动顺序:
1. setup_logging
2. discover_tasks (注册 @register_task 函数)
3. reconcile_running_logs (修复崩溃残留的 running 状态)
4. init_executor (创建协程池单例)
5. ensure_default_schedules (注册系统调度: 日志/缓存清理)
6. scheduler_loop (asyncio task, 后台调度)

ASGI 顶层结构:
    socketio.ASGIApp(sio, other_asgi_app=fastapi)
即 socketio 在最外层, /socket.io 走 sio, 其他走 fastapi。
这样 socketio 的 polling/websocket 协议都能正常握手 + upgrade。

前端托管:
    若 settings.static_dir 指向前端打包的 dist 目录, FastAPI 会:
    - /assets/* → 直接服 StaticFiles
    - /{path:path} (兜底) → 返回 index.html (Vue Router HTML5 history 模式)
    - /api/* 与 /socket.io/* 在前, 不会被 SPA 兜底吞掉
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.eventbus import sio
from app.core.logging import get_logger, setup_logging
from app.routers import (
    cache,
    cache_views,
    health,
    logs,
    metrics,
    notifications,
    schedules,
    stats,
    tasks,
)
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

    # 4. 注册默认系统调度 (日志/缓存清理), 防止数据无限增长
    from app.services.scheduler import ensure_default_schedules
    await ensure_default_schedules()

    # 5. 启动调度循环 (后台 asyncio task)
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


def _mount_spa(app: FastAPI, static_dir: str) -> None:
    """挂载前端 dist 目录: /assets/* 静态资源 + /{path} 全部兜底返回 index.html。

    必须在所有 API 路由注册之后调用, 否则 SPA 兜底会吞掉 API。
    """
    if not os.path.isdir(static_dir):
        logger.warning("static_dir not found, SPA not mounted", path=static_dir)
        return

    index_html = os.path.join(static_dir, "index.html")
    if not os.path.isfile(index_html):
        logger.warning("index.html not found in static_dir, SPA not mounted", path=static_dir)
        return

    assets_dir = os.path.join(static_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # SPA 兜底: 任何未匹配的 GET 路径返回 index.html, 让 Vue Router 接管
    # 排除 API 与 socket.io 与 metrics 前缀 (它们应已在前面路由命中, 这里只是双保险)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str, request: Request):
        if full_path.startswith(("api/", "socket.io/", "metrics", "docs", "openapi.json", "redoc")):
            raise HTTPException(status_code=404, detail="Not Found")
        # 真实文件存在的话也直接返回 (favicon.ico 等根级文件)
        candidate = os.path.join(static_dir, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(index_html)

    logger.info("SPA mounted", static_dir=static_dir)


def create_fastapi() -> FastAPI:
    fastapi_app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST 路由 — 必须在 SPA 兜底之前注册
    fastapi_app.include_router(health.router)
    fastapi_app.include_router(tasks.router)
    fastapi_app.include_router(logs.router)
    fastapi_app.include_router(stats.router)
    fastapi_app.include_router(schedules.router)
    fastapi_app.include_router(cache.router)
    fastapi_app.include_router(cache_views.router)
    fastapi_app.include_router(notifications.router)
    fastapi_app.include_router(metrics.router)

    # SPA: 前端打包后的 dist 目录, 通过环境变量 STATIC_DIR 配置
    if settings.static_dir:
        _mount_spa(fastapi_app, settings.static_dir)

    return fastapi_app


# 顶级 ASGI app: socketio 在外层, FastAPI 作为 other_asgi_app
fastapi_app = create_fastapi()
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="socket.io")
