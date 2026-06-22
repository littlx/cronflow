"""通知相关 Pydantic schema。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class NotificationConfigBase(BaseModel):
    name: str
    channel: str                       # 'webhook' | 未来 'sms' | 'email' | ...
    config: dict[str, Any] = {}        # 渠道特定配置 (webhook={url}; sms={api_key,sign,template})
    events: list[str] = []             # ['task_failed', 'task_success', ...]
    enabled: bool = True


class NotificationConfigCreate(NotificationConfigBase):
    pass


class NotificationConfigUpdate(BaseModel):
    name: str | None = None
    channel: str | None = None
    config: dict[str, Any] | None = None
    events: list[str] | None = None
    enabled: bool | None = None


class NotificationConfigOut(NotificationConfigBase):
    id: int
    created_at: str | None = None
    updated_at: str | None = None


class NotificationLogOut(BaseModel):
    id: int
    config_id: int
    event: str
    task_log_id: int | None
    status: str                        # 'success' | 'failed'
    message: str | None
    created_at: str | None
