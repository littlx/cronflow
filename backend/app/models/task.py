"""统一任务定义表 — kind=curl 等表单创建的任务入库;
python 任务由 @register_task 在内存注册, 不入库。

handler_config (JSON) 按 kind 不同字段:
  curl: {url, method, headers, data, handler_type, target_collection, timeout?}
  (未来) shell: {script, cwd, env}
  (未来) sql: {dsn, query}
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)         # uuid hex
    kind: Mapped[str] = mapped_column(String(32), nullable=False)         # 'curl' | 未来 'shell' 等
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    handler_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (Index("ix_tasks_kind", "kind"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "description": self.description or "",
            "handler_config": self.handler_config or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
