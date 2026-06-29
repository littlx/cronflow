import asyncio
import httpx
import pytest
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.task_log import TaskLog
from app.registry.decorator import register_task
from app.services.executor import init_executor


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


@pytest.mark.asyncio
async def test_executor_success(db_session):
    """测试任务正常执行成功全流程状态流转。"""
    executor = init_executor(max_concurrency=4)
    
    # 异步执行任务
    res = await executor.run("tasks.test_executor.mock_success", task_args={"x": 42})
    assert res["ok"] is True
    assert res["attempt"] == 1
    
    # 查询日志验证状态为 success
    logs = (await db_session.execute(select(TaskLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].task_ref == "tasks.test_executor.mock_success"
    assert logs[0].status == "success"
    assert logs[0].attempt == 1
    assert "value\": 42" in logs[0].result


@pytest.mark.asyncio
async def test_executor_retry_and_recover(db_session):
    """测试瞬态网络故障引发重试，并在最大次数内重试成功恢复。"""
    global retry_count
    retry_count = 0
    executor = init_executor(max_concurrency=4)
    
    res = await executor.run("tasks.test_executor.mock_retryable")
    assert res["ok"] is True
    assert res["attempt"] == 3
    
    # 验证产生了 3 次尝试记录
    logs = (await db_session.execute(select(TaskLog).order_by(TaskLog.attempt))).scalars().all()
    assert len(logs) == 3
    
    # 前两次失败
    assert logs[0].attempt == 1
    assert logs[0].status == "failed"
    assert "Mock network fluctuation" in logs[0].error
    
    assert logs[1].attempt == 2
    assert logs[1].status == "failed"
    
    # 第三次成功
    assert logs[2].attempt == 3
    assert logs[2].status == "success"
    assert logs[2].result == "recovered"


@pytest.mark.asyncio
async def test_executor_business_error(db_session):
    """测试业务 RuntimeError 抛出时，不进行任何重试，直接终态失败。"""
    executor = init_executor(max_concurrency=4)
    
    res = await executor.run("tasks.test_executor.mock_business_error")
    assert res["ok"] is False
    assert res["attempt"] == 1
    assert "Business calculation exception" in res["error"]
    
    # 验证数据库仅有 1 次失败记录
    logs = (await db_session.execute(select(TaskLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].status == "failed"
    assert logs[0].attempt == 1
    assert "RuntimeError" in logs[0].error


@pytest.mark.asyncio
async def test_executor_concurrency_and_pending(db_session):
    """测试并发受限下，排队任务能否正确落库 pending 状态，并在执行完毕后全部转换为 success。"""
    # 限制最大并发为 1
    executor = init_executor(max_concurrency=1)
    
    # 异步触发第一个慢任务
    t1 = asyncio.create_task(executor.run("tasks.test_executor.mock_slow"))
    await asyncio.sleep(0.04) # 给事件循环时间调度 t1 以占领 Semaphore
    
    # 异步触发第二个慢任务，此时它必须挂起在信号量之外排队
    t2 = asyncio.create_task(executor.run("tasks.test_executor.mock_slow"))
    await asyncio.sleep(0.04) # 给事件循环时间调度 t2 以便写入排队状态
    
    # 在任务还在并发执行和排队期间，开辟新 session 查询 DB 状态
    async with AsyncSessionLocal() as session:
        logs = (await session.execute(select(TaskLog).order_by(TaskLog.id))).scalars().all()
        assert len(logs) == 2
        # 第一个任务正在运行
        assert logs[0].status == "running"
        # 第二个任务在信号量外排队，已被成功持久化为 pending！
        assert logs[1].status == "pending"
        assert logs[1].attempt == 1

    # 等待两个并发慢任务全部执行结束
    await asyncio.gather(t1, t2)
    
    # 验证最终日志状态均已顺利转成 success 终态
    async with AsyncSessionLocal() as session:
        logs = (await session.execute(select(TaskLog).order_by(TaskLog.id))).scalars().all()
        assert len(logs) == 2
        assert logs[0].status == "success"
        assert logs[1].status == "success"
