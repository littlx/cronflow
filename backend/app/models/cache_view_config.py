"""缓存视图配置表 — 每个 target_collection 一份表格列配置。

配置内容描述了如何把 document(JSON) 渲染成分页表格:
- row_path: 行根路径; 空串/None 表示把 document 自身作为行集合
- columns:  列定义数组, 每列 {key, label, type, width?}
            key   = 在行对象上的 JSON 路径(支持 a.b.c / a[0].b)
            label = 表头中文名
            type  = text|number|datetime|boolean|json
            width = 列宽(像素), 可选
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CacheViewConfig(Base):
    __tablename__ = "cache_view_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_collection: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    row_path: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "target_collection": self.target_collection,
            "row_path": self.row_path or "",
            "columns": self.columns or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
