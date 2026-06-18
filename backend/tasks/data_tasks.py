"""业务数据类示例任务。"""
from __future__ import annotations

import time

from app.registry import register_task


@register_task(name="延时示例任务", description="休眠指定秒数后返回, 用于测试调度与日志")
def sleep_task(seconds: int = 3) -> dict:
    """休眠 seconds 秒, 模拟耗时任务。

    :param seconds: 休眠秒数, 默认 3
    """
    time.sleep(max(0, min(int(seconds), 300)))
    return {"slept": seconds}


@register_task(name="失败示例任务", description="总是抛出异常, 用于测试失败日志与重试")
def always_fail() -> dict:
    """故意失败, 测试错误处理链路。"""
    raise RuntimeError("这是一次预期内的失败, 用于验证错误日志采集")
