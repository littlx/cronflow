"""cURL handler — httpx 抓取 → 写入 JSONB 缓存表。

handler_config:
  url, method (GET|POST|...), headers (dict), data (dict|None),
  handler_type (PURE_JSON|NESTED_DATA|RAW_RESPONSE), target_collection
"""
from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models.cache import CrawledDataCache
from app.services.ref_resolver import ResolvedTask
from worker.handlers import HandlerResult


kind = "curl"


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


def execute(session: Session, resolved: ResolvedTask, task_args: dict[str, Any]) -> HandlerResult:
    cfg = resolved.handler_config or {}
    url = cfg.get("url") or ""
    method = (cfg.get("method") or "GET").upper()
    headers = cfg.get("headers") or {}
    data = cfg.get("data")
    handler_type = cfg.get("handler_type") or "PURE_JSON"
    target_collection = cfg.get("target_collection") or "default"

    if not url:
        raise RuntimeError(f"curl task {resolved.ref} 缺少 url")

    with httpx.Client(timeout=30.0) as client:
        resp = client.request(
            method=method, url=url, headers=headers,
            json=data if (data and method != "GET") else None,
        )
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
