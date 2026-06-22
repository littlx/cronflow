"""Handler 注册表 — kind -> handler 实例。

新增 kind 只需: 写一个 handler 文件 + 在此注册一行。
"""
from __future__ import annotations

from app.handlers.base import HandlerResult, TaskHandler
from app.handlers.curl_handler import curl_handler
from app.handlers.python_handler import python_handler

# kind -> handler 实例
HANDLERS: dict[str, TaskHandler] = {
    python_handler.kind: python_handler,
    curl_handler.kind: curl_handler,
}


def get_handler(kind: str) -> TaskHandler | None:
    return HANDLERS.get(kind)


__all__ = ["HandlerResult", "TaskHandler", "HANDLERS", "get_handler"]
