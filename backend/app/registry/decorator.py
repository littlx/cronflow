"""@register_task 装饰器 + 全局任务注册表。

亮点保留: 在函数上加装饰器即自动注册为可视化任务, 参数自省供前端动态表单。
task_id 规则: tasks.<module>.<func>, 与旧版一致。
"""
from __future__ import annotations

from typing import Any, Callable

from app.registry.introspect import introspect_parameters

# 全局注册表: task_id -> task definition dict (不含 func 句柄的序列化视图单独提供)
TASKS: dict[str, dict[str, Any]] = {}


def register_task(
    name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable], Callable]:
    """将一个 Python 函数注册为可调度、可在前端可视化管理的任务。"""

    def decorator(func: Callable) -> Callable:
        task_id = f"tasks.{func.__module__.split('.')[-1]}.{func.__name__}"
        display_name = name or func.__name__.replace("_", " ").title()
        desc = (description or func.__doc__ or "No description provided.").strip()
        parameters = introspect_parameters(func)

        TASKS[task_id] = {
            "id": task_id,
            "name": display_name,
            "description": desc,
            "module": func.__module__,
            "func": func,
            "parameters": parameters,
        }
        return func

    return decorator


def list_tasks() -> list[dict[str, Any]]:
    """返回不含 func 句柄的序列化视图, 供 API 使用。"""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "module": t["module"],
            "parameters": t["parameters"],
        }
        for t in TASKS.values()
    ]


def get_task(task_id: str) -> dict[str, Any] | None:
    return TASKS.get(task_id)
