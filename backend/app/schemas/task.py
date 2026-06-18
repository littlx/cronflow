"""任务相关 Pydantic schema。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TaskParameter(BaseModel):
    name: str
    type: str
    default: Any = None
    required: bool
    description: str = ""


class TaskOut(BaseModel):
    id: str
    name: str
    description: str
    module: str
    parameters: list[TaskParameter]


class TriggerTaskIn(BaseModel):
    task_id: str
    task_args: dict[str, Any] = {}
