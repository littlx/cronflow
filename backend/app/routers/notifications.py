"""通知配置 CRUD + 发送记录路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser, get_current_user
from app.schemas.notification import (
    NotificationConfigCreate,
    NotificationConfigOut,
    NotificationConfigUpdate,
)
from app.services import notification_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/configs", response_model=list[NotificationConfigOut])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    rows = await notification_service.list_configs(db)
    return [r.to_dict() for r in rows]


@router.post("/configs", response_model=NotificationConfigOut)
async def create_config(
    payload: NotificationConfigCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    cfg = await notification_service.create_config(db, payload)
    return cfg.to_dict()


@router.put("/configs/{config_id}", response_model=NotificationConfigOut)
async def update_config(
    config_id: int,
    payload: NotificationConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    cfg = await notification_service.update_config(db, config_id, payload)
    if not cfg:
        raise HTTPException(status_code=404, detail="通知配置不存在")
    return cfg.to_dict()


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    ok = await notification_service.delete_config(db, config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知配置不存在")
    return {"ok": True}


@router.get("/logs")
async def list_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    config_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return await notification_service.list_logs(db, limit, offset, config_id, status)


@router.post("/configs/{config_id}/test")
async def test_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """发一条测试消息, 验证通知配置是否生效。"""
    from app.models.notification import NotificationConfig
    cfg = await db.get(NotificationConfig, config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="通知配置不存在")
    from app.notifiers import NOTIFIERS
    notifier = NOTIFIERS.get(cfg.channel)
    if not notifier:
        raise HTTPException(status_code=400, detail=f"未注册的渠道: {cfg.channel}")
    try:
        await notifier.notify(
            event="test",
            config=cfg.config or {},
            context={"message": "这是一条来自 CronFlow 的测试通知"},
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
