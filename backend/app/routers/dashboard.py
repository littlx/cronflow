"""监控中心面板展示配置 CRUD 路由。

- GET /api/dashboard/config  → 获取配置 (如果不存在则返回包含空配置的200)
- PUT /api/dashboard/config  → 保存配置
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models.dashboard_config import DashboardConfig
from app.schemas.dashboard_config import DashboardConfigOut, DashboardConfigUpsert

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/config", response_model=DashboardConfigOut)
async def get_dashboard_config(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(DashboardConfig).where(
                DashboardConfig.username == user.username
            )
        )
    ).scalar_one_or_none()
    if not row:
        return {"username": user.username, "config": []}
    return row.to_dict()


@router.put("/config", response_model=DashboardConfigOut)
async def upsert_dashboard_config(
    payload: DashboardConfigUpsert,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(DashboardConfig).where(
                DashboardConfig.username == user.username
            )
        )
    ).scalar_one_or_none()

    config_data = [c.model_dump() for c in payload.config]
    if row is None:
        row = DashboardConfig(
            username=user.username,
            config=config_data,
        )
        db.add(row)
    else:
        row.config = config_data
    await db.commit()
    await db.refresh(row)
    return row.to_dict()
