"""抓取数据缓存表 — JSON 存储, 支持结构化检索。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CrawledDataCache(Base):
    __tablename__ = "crawled_data_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_collection: Mapped[str] = mapped_column(String(255), nullable=False)
    document: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )

    __table_args__ = (Index("ix_cache_collection_created", "target_collection", "created_at"),)


