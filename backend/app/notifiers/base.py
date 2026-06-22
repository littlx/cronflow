"""通知器接口 — 可插拔通知渠道 (扩展点)。

每个 Notifier 实现一个 channel (webhook / sms / email / dingtalk / wecom 等)。
notification_configs 表里的 channel 字段决定路由到哪个 Notifier 实例,
config 字段提供该渠道的具体配置 (如 webhook url)。

新增渠道:
1. 写一个 xxx_notifier.py 文件, 实现 Notifier.notify(event, config, context)
2. 在 __init__.py 里 NOTIFIERS["xxx"] = XxxNotifier() 注册一行
"""
from __future__ import annotations

from typing import Any, Protocol


class Notifier(Protocol):
    """通知渠道协议。"""
    name: str

    async def notify(self, event: str, config: dict[str, Any], context: dict[str, Any]) -> None:
        """发送一条通知。

        Args:
            event: 事件名 (e.g. 'task_failed', 'task_success', 'test')
            config: 该渠道实例的配置 (来自 notification_configs.config 列)
            context: 事件上下文 (e.g. {'log': {...}, 'task_ref': ...})
        """
        ...


# 渠道注册表: channel -> Notifier 实例 (由 __init__.py 填充)
NOTIFIERS: dict[str, Notifier] = {}


async def notify_event(event: str, context: dict[str, Any]) -> None:
    """对某个事件触发所有 enabled 且订阅的通知配置。

    实际派发逻辑在 notification_service.dispatch (查 DB 配置 → 调 notifier
    → 写 NotificationLog), 这里只是 executor 看到的对外入口。
    """
    try:
        from app.services.notification_service import dispatch
        await dispatch(event, context)
    except Exception:
        # 通知失败绝不能影响主路径
        from app.core.logging import get_logger
        get_logger("notifiers").exception("notify_event failed")


__all__ = ["Notifier", "NOTIFIERS", "notify_event"]
