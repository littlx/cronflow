"""任务发现 — 扫描 tasks/ 目录自动导入, 触发 @register_task 装饰器。

在 FastAPI lifespan 启动时调用一次, 注册表即填充完毕。
"""
from __future__ import annotations

import importlib
import os
import sys

from app.core.logging import get_logger

logger = get_logger("registry")


def discover_tasks(tasks_dir: str = "tasks") -> None:
    """动态导入 tasks/ 下所有 .py 模块, 触发注册装饰器。"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    target_dir = os.path.join(base_dir, tasks_dir)

    if not os.path.isdir(target_dir):
        logger.info("discover: tasks dir not found", dir=target_dir)
        return

    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    for filename in os.listdir(target_dir):
        if filename.endswith(".py") and not filename.startswith("_"):
            module_name = f"{tasks_dir}.{filename[:-3]}"
            try:
                importlib.import_module(module_name)
                logger.info("loaded task module", module=module_name)
            except Exception:
                logger.exception("failed to load task module", module=module_name)
