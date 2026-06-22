"""任务执行日志表。首版普通表 + TTL 清理任务; 按月分区留为后续迁移点。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 统一 ref 字符串: python 'tasks.<m>.<f>' / curl 'curl:<uuid>'
    task_ref: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 'manual' | 'interval' | 'cron'
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # 'running' | 'success' | 'failed'
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # 第几次尝试: 1=首次, 2=第一次重试, ... (重试时新建行而非覆盖)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)  # 秒
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_ref": self.task_ref,
            "task_name": self.task_name,
            "trigger_type": self.trigger_type,
            "schedule_id": self.schedule_id,
            "status": self.status,
            "attempt": self.attempt,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration": self.duration,
            "result": self.result,
            "error": self.error,
        }
