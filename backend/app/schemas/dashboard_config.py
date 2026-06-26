from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DashboardTableConfigSchema(BaseModel):
    collection: str
    width: Literal["third", "half", "full"]
    visibleColumns: list[str] = Field(default_factory=list)


class DashboardConfigUpsert(BaseModel):
    """PUT /api/dashboard/config 请求体。"""

    config: list[DashboardTableConfigSchema] = Field(default_factory=list)


class DashboardConfigOut(DashboardConfigUpsert):
    username: str
    created_at: str | None = None
    updated_at: str | None = None
