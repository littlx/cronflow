"""缓存视图(表格列)配置 Pydantic schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CellType = Literal["text", "number", "datetime", "boolean", "json"]


SummaryType = Literal["none", "sum", "avg", "min", "max", "count"]


class CacheColumnConfig(BaseModel):
    """单列定义。

    key   — 在行对象上的 JSON 路径(支持 a.b.c / a[0].b)
    label — 表头显示
    type  — 单元格渲染类型
    width — 列宽(像素), 可选
    summary_type — 合计类型, 可选
    """

    key: str
    label: str
    type: CellType = "text"
    width: int | None = None
    summary_type: SummaryType | None = None


class CacheViewConfigUpsert(BaseModel):
    """PUT /api/cache-views/{collection} 请求体。"""

    row_path: str = Field(default="", description="行根路径; 空表示 document 自身")
    columns: list[CacheColumnConfig] = Field(default_factory=list)


class CacheViewConfigOut(CacheViewConfigUpsert):
    target_collection: str
    created_at: str | None = None
    updated_at: str | None = None
