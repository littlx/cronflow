"""cURL/API 同步任务配置表。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CurlTask(Base):
    __tablename__ = "curl_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # uuid
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)  # 轮询间隔
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 'PURE_JSON' | 'NESTED_DATA' | 'RAW_RESPONSE'
    handler_type: Mapped[str] = mapped_column(String(50), default="PURE_JSON")
    target_collection: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # 请求配置
    url: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="GET")
    headers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # 执行状态
    status: Mapped[str] = mapped_column(String(50), default="idle")  # idle|running|error
    last_run_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_run_result: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "minutes": self.minutes,
            "is_enabled": self.is_enabled,
            "handler_type": self.handler_type,
            "target_collection": self.target_collection,
            "request_config": {
                "url": self.url,
                "method": self.method,
                "headers": self.headers or {},
                "data": self.data,
            },
            "status": self.status,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "next_run_time": self.next_run_time.isoformat() if self.next_run_time else None,
            "last_run_result": self.last_run_result,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
