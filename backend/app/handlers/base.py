"""Task handler 协议。

每个 handler 负责一个 kind 的具体执行逻辑, 返回 HandlerResult。
不负责日志/重试/emit, 这些由 executor 统一处理。

handler.execute 必须是 async 函数, 返回 HandlerResult。
内部对同步阻塞函数 (如 time.sleep) 用 asyncio.to_thread 包装, 不阻塞 event loop。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ref_resolver import ResolvedTask


@dataclass
class HandlerResult:
    """handler 执行结果。result_text 进 task_logs.result; extra 给 emit 透传。"""
    result_text: str
    extra: dict[str, Any] = field(default_factory=dict)


class TaskHandler:
    """handler 基类。子类实现 kind 与 execute。"""
    kind: str = ""

    async def execute(
        self,
        session: AsyncSession,
        resolved: ResolvedTask,
        task_args: dict[str, Any],
    ) -> HandlerResult:
        raise NotImplementedError
