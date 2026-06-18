"""Python handler — 执行 @register_task 注册的函数。"""
from __future__ import annotations

import inspect
from typing import Any

from sqlalchemy.orm import Session

from app.registry import get_task as get_python_task
from app.registry.introspect import coerce_arg
from app.services.ref_resolver import ResolvedTask
from worker.handlers import HandlerResult


kind = "python"


def _build_kwargs(func, task_args: dict) -> dict:
    sig = inspect.signature(func)
    kwargs: dict = {}
    for name, param in sig.parameters.items():
        if name in task_args:
            kwargs[name] = coerce_arg(task_args[name], param.annotation)
        elif param.default is not inspect.Parameter.empty:
            kwargs[name] = param.default
    return kwargs


def execute(session: Session, resolved: ResolvedTask, task_args: dict[str, Any]) -> HandlerResult:
    """通过注册表查到函数 → 入参类型转换 → 调用 → 返回 result。"""
    t = get_python_task(resolved.ref)
    if not t:
        raise RuntimeError(f"python task not in registry: {resolved.ref}")
    func = t["func"]
    kwargs = _build_kwargs(func, task_args)
    result = func(**kwargs) if kwargs else func()
    return HandlerResult(result_text=str(result)[:8000])
