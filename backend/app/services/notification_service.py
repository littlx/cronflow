"""通知配置 CRUD + 写日志。

executor 失败/成功时调 notify_event(event, context), 该模块查 enabled
且事件匹配的所有配置, 转给对应 notifier 实例发送, 并写一行 NotificationLog
便于排查。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.notification import NotificationConfig, NotificationLog
from app.schemas.notification import NotificationConfigCreate, NotificationConfigUpdate

logger = get_logger("notification_service")


async def list_configs(db: AsyncSession) -> list[NotificationConfig]:
    rows = (
        await db.execute(select(NotificationConfig).order_by(NotificationConfig.id))
    ).scalars().all()
    return list(rows)


async def create_config(db: AsyncSession, payload: NotificationConfigCreate) -> NotificationConfig:
    cfg = NotificationConfig(
        name=payload.name,
        channel=payload.channel,
        config=payload.config,
        events=payload.events,
        enabled="1" if payload.enabled else "0",
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


async def update_config(
    db: AsyncSession, config_id: int, payload: NotificationConfigUpdate
) -> NotificationConfig | None:
    cfg = await db.get(NotificationConfig, config_id)
    if not cfg:
        return None
    if payload.name is not None: cfg.name = payload.name
    if payload.channel is not None: cfg.channel = payload.channel
    if payload.config is not None: cfg.config = payload.config
    if payload.events is not None: cfg.events = payload.events
    if payload.enabled is not None: cfg.enabled = "1" if payload.enabled else "0"
    await db.commit()
    await db.refresh(cfg)
    return cfg


async def delete_config(db: AsyncSession, config_id: int) -> bool:
    cfg = await db.get(NotificationConfig, config_id)
    if not cfg:
        return False
    await db.delete(cfg)
    await db.commit()
    return True


# ---- 通知日志查询 ----

async def list_logs(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    config_id: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    base = select(NotificationLog)
    count_base = select(func.count(NotificationLog.id))

    def _where(stmt):
        if config_id is not None:
            stmt = stmt.where(NotificationLog.config_id == config_id)
        if status:
            stmt = stmt.where(NotificationLog.status == status)
        return stmt

    total = (await db.execute(_where(count_base))).scalar() or 0
    rows = (
        await db.execute(
            _where(base).order_by(desc(NotificationLog.created_at)).offset(offset).limit(limit)
        )
    ).scalars().all()
    return {
        "items": [r.to_dict() for r in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


# ---- 派发: executor 调 notify(...) → 这里查配置并触发 notifier ----

async def dispatch(event: str, context: dict[str, Any]) -> None:
    """对所有 enabled 且订阅了 event 的配置触发对应渠道的 notifier。"""
    from app.notifiers import NOTIFIERS

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(NotificationConfig).where(NotificationConfig.enabled == "1")
            )
        ).scalars().all()

        for cfg in rows:
            events = cfg.events or []
            if events and event not in events:
                continue
            notifier = NOTIFIERS.get(cfg.channel)
            if not notifier:
                logger.warning("no notifier for channel", channel=cfg.channel)
                continue

            log_status = "success"
            log_msg: str | None = None
            try:
                await notifier.notify(event=event, config=cfg.config or {}, context=context)
            except Exception as e:
                log_status = "failed"
                log_msg = f"{type(e).__name__}: {e}"
                logger.warning(
                    "notifier failed", channel=cfg.channel, config_id=cfg.id, error=str(e)
                )

            # 任务日志 id 透传 (executor 传入 context['log']['id'])
            task_log_id: int | None = None
            try:
                task_log_id = int(context.get("log", {}).get("id"))
            except Exception:
                task_log_id = None

            db.add(NotificationLog(
                config_id=cfg.id,
                event=event,
                task_log_id=task_log_id,
                status=log_status,
                message=log_msg,
            ))
        await db.commit()
