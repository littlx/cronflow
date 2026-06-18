"""Task handler 协议。

每个 handler 负责一个 kind 的具体执行逻辑, 返回 (result_str, extra_log_fields)。
不负责日志/重试/emit, 这些由 task_runner 统一处理。
"""
from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.services.ref_resolver import ResolvedTask


class HandlerResult:
    """handler 执行结果。result_text 进 task_logs.result; extra 给 emit 透传。"""
    def __init__(self, result_text: str, extra: dict[str, Any] | None = None):
        self.result_text = result_text
        self.extra = extra or {}


class TaskHandler(Protocol):
    kind: str

    def execute(
        self,
        session: Session,
        resolved: ResolvedTask,
        task_args: dict[str, Any],
    ) -> HandlerResult:
        ...
