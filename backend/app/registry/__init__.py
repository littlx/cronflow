from app.registry.decorator import TASKS, get_task, list_tasks, register_task
from app.registry.discover import discover_tasks
from app.registry.introspect import coerce_arg

__all__ = ["TASKS", "get_task", "list_tasks", "register_task", "discover_tasks", "coerce_arg"]
