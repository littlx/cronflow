"""统一任务相关 Pydantic schema。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TaskParameter(BaseModel):
    name: str
    type: str
    default: Any = None
    required: bool
    description: str = ""


class TaskOut(BaseModel):
    """统一任务视图: python (注册表) + curl (DB)。"""
    ref: str                              # python: 'tasks.xxx.foo'; curl: 'curl:<uuid>'
    kind: str                             # 'python' | 'curl'
    name: str
    description: str = ""
    handler_config: dict[str, Any] = {}
    parameters: list[TaskParameter] = []
    # curl-only:
    id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    # python-only:
    module: str | None = None


class CurlHandlerConfig(BaseModel):
    url: str
    method: str = "GET"
    headers: dict[str, str] = {}
    data: dict[str, Any] | str | None = None   # dict (JSON body) | str (form/raw) | None
    handler_type: str = "PURE_JSON"          # PURE_JSON | NESTED_DATA | RAW_RESPONSE
    target_collection: str


class CurlTaskCreate(BaseModel):
    name: str
    description: str | None = None
    handler_config: CurlHandlerConfig


class CurlTaskUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    handler_config: CurlHandlerConfig | None = None


class TriggerTaskIn(BaseModel):
    """立即触发: 用 ref 引用任意 kind 的任务。"""
    task_ref: str
    task_args: dict[str, Any] = {}
