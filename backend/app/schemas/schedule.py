"""调度相关 Pydantic schema。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ScheduleBase(BaseModel):
    task_ref: str
    name: str
    trigger_type: str                   # interval | cron
    trigger_args: dict[str, Any] = {}
    task_args: dict[str, Any] = {}


class ScheduleCreate(ScheduleBase):
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: str | None = None
    trigger_type: str | None = None
    trigger_args: dict[str, Any] | None = None
    task_args: dict[str, Any] | None = None
    enabled: bool | None = None


class ScheduleOut(BaseModel):
    id: int
    task_ref: str
    name: str
    trigger_type: str
    trigger_args: dict[str, Any]
    task_args: dict[str, Any]
    enabled: bool
    # 由路由从 redbeat 实时计算填充, 不来自 DB
    next_run_time: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
