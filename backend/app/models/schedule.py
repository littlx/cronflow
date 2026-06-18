"""定时调度配置表 — DB 为唯一真相源, redbeat 负责到点分发。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobSchedule(Base):
    __tablename__ = "job_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 'python' | 'curl'
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, default="python")
    # 'interval' | 'cron'
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # redbeat 调度参数 (interval: {seconds/minutes/...}; cron: {minute/hour/...})
    trigger_args: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # 任务执行参数 (python: 函数 kwargs; curl: 忽略)
    task_args: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # redbeat 中的 entry key, 用于动态增删
    redbeat_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    next_run_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        # 调度器查"到期且启用"的任务
        Index("ix_schedules_enabled_next_run", "enabled", "next_run_time"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type,
            "trigger_type": self.trigger_type,
            "trigger_args": self.trigger_args or {},
            "task_args": self.task_args or {},
            "enabled": self.enabled,
            "redbeat_key": self.redbeat_key,
            "next_run_time": self.next_run_time.isoformat() if self.next_run_time else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
