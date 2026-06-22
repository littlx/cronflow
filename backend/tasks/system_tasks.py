"""系统监控类示例任务。

cleanup_old_logs 演示了 async handler: executor 会自动识别 async 函数并 await。
同步 handler (如 system_health_check) 会被 asyncio.to_thread 包装, 不阻塞 event loop。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.core.db import AsyncSessionLocal
from app.models.task_log import TaskLog
from app.registry import register_task


@register_task(name="系统健康检查", description="采集当前进程的 CPU 与内存占用并返回")
def system_health_check() -> dict:
    """检查系统运行状态, 返回 CPU/内存/磁盘占用。"""
    import psutil

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }


@register_task(name="清理过期日志", description="按保留天数清理 task_logs 中的过期记录")
async def cleanup_old_logs(keep_days: int = 90) -> dict:
    """清理超过 keep_days 天的执行日志。

    :param keep_days: 保留天数, 默认 90
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    async with AsyncSessionLocal() as session:
        result = await session.execute(delete(TaskLog).where(TaskLog.started_at < cutoff))
        await session.commit()
        return {"deleted": result.rowcount or 0, "cutoff": cutoff.isoformat()}
