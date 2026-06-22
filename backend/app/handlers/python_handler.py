"""Python handler — 执行 @register_task 注册的函数。

支持 sync 与 async 两种注册函数:
- async 函数: 直接 await (如 cleanup_old_logs)
- sync 函数: 用 asyncio.to_thread 包装, 不阻塞 event loop (如 system_health_check)
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.registry import get_task as get_python_task
from app.registry.introspect import coerce_arg
from app.services.ref_resolver import ResolvedTask
from app.handlers.base import HandlerResult, TaskHandler

logger = get_logger("handler.python")


class PythonHandler(TaskHandler):
    kind = "python"

    def _build_kwargs(self, func, task_args: dict) -> dict:
        sig = inspect.signature(func)
        kwargs: dict = {}
        for name, param in sig.parameters.items():
            if name in task_args:
                kwargs[name] = coerce_arg(task_args[name], param.annotation)
            elif param.default is not inspect.Parameter.empty:
                kwargs[name] = param.default
        return kwargs

    async def execute(
        self,
        session: AsyncSession,
        resolved: ResolvedTask,
        task_args: dict[str, Any],
    ) -> HandlerResult:
        t = get_python_task(resolved.ref)
        if not t:
            raise RuntimeError(f"python task not in registry: {resolved.ref}")
        func = t["func"]
        kwargs = self._build_kwargs(func, task_args)

        if inspect.iscoroutinefunction(func):
            result = await func(**kwargs) if kwargs else await func()
        else:
            # 同步函数用 to_thread 包装, 避免阻塞 event loop
            result = await asyncio.to_thread(func, **kwargs) if kwargs else await asyncio.to_thread(func)

        return HandlerResult(result_text=str(result)[:8000])


python_handler = PythonHandler()
