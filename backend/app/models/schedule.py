"""定时调度表 — task_ref 是字符串:
- python kind: 形如 'tasks.system_tasks.system_health_check' (注册表 id)
- curl  kind: 形如 'curl:<uuid>' (引用 tasks 表的 id)

next_run_time 是 DB 真相源, 调度循环扫表 WHERE next_run_time <= now()。
更新/启停调度时由 schedule_service 重算 next_run_time。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, JSON, String
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
    trigger_args: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # python 任务的 kwargs; curl 不用 (handler_config 已含全部参数)
    task_args: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 调度真相源: 到点由 scheduler 更新为下一次时间
    next_run_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (Index("ix_schedules_enabled", "enabled"),)


