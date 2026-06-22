"""通知记录表 — 为短信/邮件/Webhook 等通知渠道预留。

首版只实现 webhook notifier, 但表结构一次到位。
notifications 表记录每次通知的发送结果, 便于排查与重发。
notification_configs 表存储各渠道的配置 (url / api_key / 模板 等)。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotificationConfig(Base):
    """通知渠道配置: 一条记录 = 一个渠道实例 (webhook url / 短信 api 等)。"""
    __tablename__ = "notification_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 'webhook' | 未来 'sms' | 'email' | 'dingtalk' | 'wecom'
    channel: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # 渠道相关配置: webhook={url}; sms={api_key,sign,template}; ...
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # 触发事件: ['task_failed', 'task_success', ...]
    events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(
        String(1), default="1", nullable=False, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "channel": self.channel,
            "config": self.config or {},
            "events": self.events or [],
            "enabled": self.enabled == "1" or self.enabled is True,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class NotificationLog(Base):
    """通知发送记录, 一条 = 一次发送尝试。"""
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # 触发事件: 'task_failed' | 'task_success' | ...
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    # 关联的任务日志 (便于追溯)
    task_log_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # 'success' | 'failed'
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    # 发送详情 / 错误信息
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "config_id": self.config_id,
            "event": self.event,
            "task_log_id": self.task_log_id,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
