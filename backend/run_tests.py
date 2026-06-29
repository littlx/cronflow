import asyncio
from datetime import datetime, timezone
import time
import httpx
import unittest

from app.core.config import settings

# 1. 覆盖数据库 URL 为内存库，降低重试间隔以加速测试
settings.database_url = "sqlite+aiosqlite:///:memory:"
settings.task_retry_max = 2
settings.task_retry_backoff = 0.05  # 退避时间缩短到 50ms 方便测试

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

# 创建测试专属 engine
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
from app.models.task_log import TaskLog
from app.registry.decorator import register_task, TASKS
from app.services.executor import init_executor

# 禁用 socketio emit 的网络消耗，在测试里 mock 掉
import app.core.eventbus
async def mock_emit(event, data):
    pass
app.core.eventbus.emit = mock_emit


# 注册测试专属任务
@register_task(name="测试正常成功任务")
async def mock_success(x: int) -> dict:
    return {"status": "ok", "value": x}

retry_count = 0
@register_task(name="测试瞬态可重试任务")
async def mock_retryable() -> str:
    global retry_count
    retry_count += 1
    if retry_count < 3:
        raise httpx.RequestError("Mock network fluctuation")
    return "recovered"

@register_task(name="测试业务终态错误任务")
async def mock_business_error():
    raise RuntimeError("Business calculation exception")

@register_task(name="测试并发慢任务")
async def mock_slow():
    await asyncio.sleep(0.2)
    return "done"


class TestCronFlowRegistry(unittest.TestCase):
    """测试参数自省描述提取"""

    def test_parameter_introspection(self):
        # 1. 注册无类型描述的任务
        @register_task(name="Introspect No Types")
        def task_no_types(path: str, count: int = 10):
            """
            :param path: 保存文件的物理路径
            :param count: 循环计数值
            """
            pass

        # 2. 注册带类型描述的任务
        @register_task(name="Introspect With Types")
        def task_with_types(url: str, timeout: float = 3.5):
            """
            :param str url: 请求的目标链接地址
            :param float timeout: 连接超时阈值
            """
            pass

        # 验证任务 1
        ref1 = f"tasks.{task_no_types.__module__.split('.')[-1]}.task_no_types"
        t1 = TASKS.get(ref1)
        assert t1 is not None, "Introspect No Types 注册失败"
        params1 = t1["parameters"]
        self.assertEqual(len(params1), 2)
        self.assertEqual(params1[0]["name"], "path")
        self.assertEqual(params1[0]["description"], "保存文件的物理路径")
        self.assertEqual(params1[1]["name"], "count")
        self.assertEqual(params1[1]["description"], "循环计数值")

        # 验证任务 2
        ref2 = f"tasks.{task_with_types.__module__.split('.')[-1]}.task_with_types"
        t2 = TASKS.get(ref2)
        assert t2 is not None, "Introspect With Types 注册失败"
        params2 = t2["parameters"]
        self.assertEqual(len(params2), 2)
        self.assertEqual(params2[0]["name"], "url")
        self.assertEqual(params2[0]["description"], "请求的目标链接地址")
        self.assertEqual(params2[1]["name"], "timeout")
        self.assertEqual(params2[1]["description"], "连接超时阈值")


class TestCronFlowExecutor(unittest.IsolatedAsyncioTestCase):
    """测试异步执行器和两阶段提交状态"""

    async def asyncSetUp(self):
        # 每个测试开始前重建表结构
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        self.db = TestingSessionLocal()
        self.mod = mock_success.__module__.split('.')[-1]

    async def asyncTearDown(self):
        await self.db.close()
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def test_executor_success(self):
        """测试任务正常执行成功全流程状态流转。"""
        executor = init_executor(max_concurrency=4)
        ref = f"tasks.{self.mod}.mock_success"
        res = await executor.run(ref, task_args={"x": 42})
        self.assertTrue(res["ok"])
        self.assertEqual(res["attempt"], 1)

        logs = (await self.db.execute(select(TaskLog))).scalars().all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].task_ref, ref)
        self.assertEqual(logs[0].status, "success")
        self.assertEqual(logs[0].attempt, 1)
        self.assertIn("'value': 42", logs[0].result)

    async def test_executor_retry_and_recover(self):
        """测试瞬态网络故障引发重试，并在最大次数内重试成功恢复。"""
        global retry_count
        retry_count = 0
        executor = init_executor(max_concurrency=4)

        ref = f"tasks.{self.mod}.mock_retryable"
        res = await executor.run(ref)
        self.assertTrue(res["ok"])
        self.assertEqual(res["attempt"], 3)

        logs = (await self.db.execute(select(TaskLog).order_by(TaskLog.attempt))).scalars().all()
        self.assertEqual(len(logs), 3)

        self.assertEqual(logs[0].attempt, 1)
        self.assertEqual(logs[0].status, "failed")
        self.assertIn("Mock network fluctuation", logs[0].error)

        self.assertEqual(logs[1].attempt, 2)
        self.assertEqual(logs[1].status, "failed")

        self.assertEqual(logs[2].attempt, 3)
        self.assertEqual(logs[2].status, "success")
        self.assertEqual(logs[2].result, "recovered")

    async def test_executor_business_error(self):
        """测试业务 RuntimeError 抛出时，不进行任何重试，直接终态失败。"""
        executor = init_executor(max_concurrency=4)

        ref = f"tasks.{self.mod}.mock_business_error"
        res = await executor.run(ref)
        self.assertFalse(res["ok"])
        self.assertEqual(res["attempt"], 1)
        self.assertIn("Business calculation exception", res["error"])

        logs = (await self.db.execute(select(TaskLog))).scalars().all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].status, "failed")
        self.assertEqual(logs[0].attempt, 1)
        self.assertIn("RuntimeError", logs[0].error)

    async def test_executor_concurrency_and_pending(self):
        """测试并发受限下，排队任务能否正确落库 pending 状态，并在执行完毕后全部转换为 success。"""
        executor = init_executor(max_concurrency=1)

        t1 = asyncio.create_task(executor.run(f"tasks.{self.mod}.mock_slow"))
        await asyncio.sleep(0.04)

        t2 = asyncio.create_task(executor.run(f"tasks.{self.mod}.mock_slow"))
        await asyncio.sleep(0.04)

        async with TestingSessionLocal() as session:
            logs = (await session.execute(select(TaskLog).order_by(TaskLog.id))).scalars().all()
            self.assertEqual(len(logs), 2)
            self.assertEqual(logs[0].status, "running")
            # 信号量外排队：确为 pending！
            self.assertEqual(logs[1].status, "pending")
            self.assertEqual(logs[1].attempt, 1)

        await asyncio.gather(t1, t2)

        async with TestingSessionLocal() as session:
            logs = (await session.execute(select(TaskLog).order_by(TaskLog.id))).scalars().all()
            self.assertEqual(len(logs), 2)
            self.assertEqual(logs[0].status, "success")
            self.assertEqual(logs[1].status, "success")


if __name__ == "__main__":
    unittest.main()
