"""Webhook 通知渠道 — POST JSON 到指定 URL。

config:
  url: 必填, 目标 webhook URL
  method: 可选, 默认 POST
  headers: 可选, 额外请求头
  timeout: 可选, 秒数, 默认 10

发送 payload:
  { event: str, context: {...} }
"""
from __future__ import annotations

from typing import Any

import httpx


class WebhookNotifier:
    name = "webhook"

    async def notify(self, event: str, config: dict[str, Any], context: dict[str, Any]) -> None:
        url = config.get("url")
        if not url:
            raise RuntimeError("webhook 配置缺少 url")
        method = (config.get("method") or "POST").upper()
        headers = config.get("headers") or {}
        timeout = float(config.get("timeout") or 10)

        payload = {"event": event, "context": context}

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method=method, url=url, headers=headers, json=payload,
            )
            # 4xx/5xx 都视为发送失败 (上层会记 NotificationLog)
            resp.raise_for_status()


webhook_notifier = WebhookNotifier()
