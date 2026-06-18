"""cURL 任务相关 Pydantic schema。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RequestConfig(BaseModel):
    url: str
    method: str = "GET"
    headers: dict[str, str] = {}
    data: dict[str, Any] | None = None


class CurlTaskCreate(BaseModel):
    name: str
    minutes: int = 5
    is_enabled: bool = True
    handler_type: str = "PURE_JSON"   # PURE_JSON | NESTED_DATA | RAW_RESPONSE
    target_collection: str
    request_config: RequestConfig


class CurlTaskUpdate(BaseModel):
    name: str | None = None
    minutes: int | None = None
    is_enabled: bool | None = None
    handler_type: str | None = None
    target_collection: str | None = None
    request_config: RequestConfig | None = None


class CurlTaskOut(BaseModel):
    id: str
    name: str
    minutes: int
    is_enabled: bool
    handler_type: str
    target_collection: str
    request_config: RequestConfig
    status: str
    last_run_time: str | None = None
    next_run_time: str | None = None
    last_run_result: str | None = None
    error_message: str | None = None
    created_at: str | None = None
