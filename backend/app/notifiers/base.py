"""通知器接口 — 可插拔通知渠道 (扩展点)。

首版只占位: notify_event 不做任何事, 阶段3接入 webhook/短信等实现。
新增渠道只加一个 notifier 文件 + 在 NOTIFIERS 注册一行, 不改主干。
"""
from __future__ import annotations

from typing import Protocol


class Notifier(Protocol):
    name: str

    async def notify(self, event: str, context: dict) -> None:
        ...


# 渠道注册表: name -> Notifier (阶段3填充)
NOTIFIERS: dict[str, Notifier] = {}


async def notify_event(event: str, context: dict) -> None:
    """对某个事件触发所有已注册且匹配的通知器。

    首版 NOTIFIERS 为空, 此函数为 no-op。阶段3接入实际渠道。
    """
    for notifier in NOTIFIERS.values():
        try:
            await notifier.notify(event, context)
        except Exception:
            pass


__all__ = ["Notifier", "NOTIFIERS", "notify_event"]
