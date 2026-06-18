"""定时调度表 — task_ref 是字符串:
- python kind: 形如 'tasks.system_tasks.system_health_check' (注册表 id)
- curl  kind: 形如 'curl:<uuid>' 或纯 uuid (引用 tasks 表的 id)

调度层不再分叉 task_type, 由 task_ref 解析为对应 kind 后分派。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobSchedule(Base):
    __tablename__ = "job_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_ref: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 'interval' | 'cron'
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_args: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # python 任务的 kwargs; curl 不用 (handler_config 已含全部参数)
    task_args: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
        Index("ix_schedules_enabled_next_run", "enabled", "next_run_time"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_ref": self.task_ref,
            "name": self.name,
            "trigger_type": self.trigger_type,
            "trigger_args": self.trigger_args or {},
            "task_args": self.task_args or {},
            "enabled": self.enabled,
            "redbeat_key": self.redbeat_key,
            "next_run_time": self.next_run_time.isoformat() if self.next_run_time else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
