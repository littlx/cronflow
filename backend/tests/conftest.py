import asyncio
from datetime import datetime, timezone
import pytest

from app.core.config import settings

# 1. 覆盖数据库 URL 为内存库，降低重试间隔以加速测试
settings.database_url = "sqlite+aiosqlite:///:memory:"
settings.task_retry_max = 2
settings.task_retry_backoff = 0.05  # 退避时间缩短到 50ms 方便测试

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

# 创建测试专属 engine 并在 aiosqlite 连接上使用 StaticPool 以共享内存库
test_engine = create_async_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 2. 动态替换 db 模块全局单例
import app.core.db
app.core.db.engine = test_engine
app.core.db.AsyncSessionLocal = TestingSessionLocal

from app.core.db import Base

# 禁用 socketio emit 的网络消耗，在测试里 mock 掉
import app.core.eventbus
async def mock_emit(event, data):
    pass
app.core.eventbus.emit = mock_emit


@pytest.fixture(scope="session")
def event_loop():
    """创建一个 Session 级的事件循环。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def init_db():
    """每个测试函数执行前，重建全部表结构以确保数据库隔离。"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    """提供一个测试专用的 AsyncSession。"""
    async with TestingSessionLocal() as session:
        yield session
