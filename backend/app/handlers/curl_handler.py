"""cURL handler — httpx.AsyncClient 异步抓取 → 写入 JSON 缓存表。

handler_config:
  url, method (GET|POST|...), headers (dict), data (dict|str|None),
  handler_type (PURE_JSON|NESTED_DATA|RAW_RESPONSE), target_collection, timeout?

错误处理 (修复旧版问题):
- 4xx: 视为业务错误, raise RuntimeError (终态失败, 不重试)
- 5xx: raise httpx.HTTPStatusError (瞬态故障, 可重试)
- 网络错误 (TimeoutException/ConnectError): 瞬态故障, 可重试
"""
from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.cache import CrawledDataCache
from app.services.ref_resolver import ResolvedTask
from app.handlers.base import HandlerResult, TaskHandler

logger = get_logger("handler.curl")


def _process_response(handler_type: str, status_code: int, body):
    if handler_type == "RAW_RESPONSE":
        return {"_raw": body if isinstance(body, str) else str(body), "_status": status_code}
    if isinstance(body, (dict, list)):
        if handler_type == "NESTED_DATA" and isinstance(body, dict):
            for key in ("data", "result", "items", "list", "results"):
                if key in body and isinstance(body[key], (list, dict)):
                    return body[key]
        return body
    return {"_text": str(body)[:8000], "_status": status_code}


class CurlHandler(TaskHandler):
    kind = "curl"

    async def execute(
        self,
        session: AsyncSession,
        resolved: ResolvedTask,
        task_args: dict[str, Any],
    ) -> HandlerResult:
        cfg = resolved.handler_config or {}
        url = cfg.get("url") or ""
        method = (cfg.get("method") or "GET").upper()
        headers = cfg.get("headers") or {}
        data = cfg.get("data")
        handler_type = cfg.get("handler_type") or "PURE_JSON"
        target_collection = cfg.get("target_collection") or "default"
        # 超时可配 (修复旧版硬编码 30s 问题)
        timeout = float(cfg.get("timeout") or settings.task_default_timeout)

        if not url:
            raise RuntimeError(f"curl task {resolved.ref} 缺少 url")

        req_kwargs: dict = {"method": method, "url": url, "headers": headers, "timeout": timeout}
        if data and method != "GET":
            if isinstance(data, (dict, list)):
                req_kwargs["json"] = data
            else:
                # 字符串 body (form-urlencoded / raw); 若未显式声明 Content-Type, 默认 form
                req_kwargs["content"] = str(data)
                if not any(k.lower() == "content-type" for k in headers):
                    headers["Content-Type"] = "application/x-www-form-urlencoded"

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(**req_kwargs)

        # 4xx 是业务错误 (URL 错/token 过期等), 终态失败不重试
        if 400 <= resp.status_code < 500:
            raise RuntimeError(
                f"curl 请求返回 4xx: {resp.status_code} {resp.reason_phrase} — {resp.text[:500]}"
            )
        # 5xx 抛 HTTPStatusError, 由 executor 判定为瞬态可重试
        resp.raise_for_status()

        try:
            body = resp.json()
        except Exception:
            body = resp.text

        document = _process_response(handler_type, resp.status_code, body)
        session.add(CrawledDataCache(target_collection=target_collection, document=document))

        return HandlerResult(
            result_text=f"cached to {target_collection} (http {resp.status_code})",
            extra={"target_collection": target_collection, "status": resp.status_code},
        )


curl_handler = CurlHandler()
