"""异步数据库 engine 与 session — SQLite (aiosqlite) + WAL 模式。

单进程架构, async session 贯穿 API/executor/scheduler。
WAL 模式让读写不互相阻塞, 3 人 + 调度量完全够用。

时间字段统一存 aware UTC datetime; SQLite 不保留 tzinfo, 读取时由
_to_aware 统一补 UTC, 避免下游比较时 naive/aware 混用报错。
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


from typing import Any

class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""

    def to_dict(self) -> dict[str, Any]:
        """通用的 ORM 序列化为 dict 的方法。"""
        out = {}
        for column in self.__table__.columns:
            val = getattr(self, column.name)
            if isinstance(val, datetime):
                out[column.name] = val.isoformat()
            elif val is None:
                try:
                    py_type = column.type.python_type
                except NotImplementedError:
                    py_type = None

                if py_type is dict:
                    out[column.name] = {}
                elif py_type is list:
                    out[column.name] = []
                else:
                    out[column.name] = None
            else:
                out[column.name] = val
        return out


engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    """每个连接建立时开 WAL + busy_timeout, 提升并发写友好度。"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖: 提供一个异步 session, 请求结束自动关闭。"""
    async with AsyncSessionLocal() as session:
        yield session


def to_aware(dt: datetime | None) -> datetime | None:
    """SQLite 读出的 datetime 是 naive, 统一补 UTC。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
