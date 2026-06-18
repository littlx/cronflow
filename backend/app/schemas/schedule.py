"""调度相关 Pydantic schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ScheduleBase(BaseModel):
    task_id: str
    name: str
    task_type: str = "python"          # python | curl
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
    task_id: str
    name: str
    task_type: str
    trigger_type: str
    trigger_args: dict[str, Any]
    task_args: dict[str, Any]
    enabled: bool
    redbeat_key: str | None = None
    next_run_time: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
