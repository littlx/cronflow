"""同步数据库 engine 与 session — 供 Celery worker 使用。

worker 在 Celery 线程/进程池中运行, 用同步 session 更简单可靠。
共享同一套 ORM 模型 (Base / models)。
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.db import Base  # 复用模型基类与 metadata

sync_engine = create_engine(
    settings.database_url_sync,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    future=True,
)


def get_sync_session() -> Session:
    """worker 内获取同步 session 的便捷函数。调用方负责 close。"""
    return SyncSessionLocal()
