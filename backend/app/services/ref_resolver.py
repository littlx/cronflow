"""task_ref 解析: 字符串 → (kind, definition)。

约定:
- python kind: ref 形如 'tasks.<module>.<func>' (注册表 id, 字面量)
- curl   kind: ref 形如 'curl:<uuid>' 或裸 uuid (引用 tasks 表)

外部调用 resolve_ref_sync (worker) / resolve_ref_async (API) 拿到统一的 ResolvedTask。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.task import Task
from app.registry import get_task as get_python_task

CURL_PREFIX = "curl:"


@dataclass
class ResolvedTask:
    ref: str
    kind: str               # 'python' | 'curl' | ...
    name: str
    description: str
    handler_config: dict[str, Any]   # python: {} ; curl: {url, method, ...}
    parameters: list[dict] = field(default_factory=list)  # python 自省结果; curl 为空
    queue: str | None = None         # 任务级路由
    priority: int | None = None      # 任务级优先级


def _looks_like_python_ref(ref: str) -> bool:
    return ref.startswith("tasks.") and ":" not in ref


def _curl_id_from_ref(ref: str) -> str | None:
    if ref.startswith(CURL_PREFIX):
        return ref[len(CURL_PREFIX):]
    # 兼容: 裸 uuid 也当作 curl
    if len(ref) in (32, 36) and "." not in ref:
        return ref
    return None


def _python_resolved(task_id: str) -> ResolvedTask | None:
    t = get_python_task(task_id)
    if not t:
        return None
    return ResolvedTask(
        ref=task_id,
        kind="python",
        name=t["name"],
        description=t["description"],
        handler_config={},
        parameters=t["parameters"],
        queue=t.get("queue"),
        priority=t.get("priority"),
    )


def _curl_resolved_from_row(row: Task) -> ResolvedTask:
    cfg = row.handler_config or {}
    return ResolvedTask(
        ref=f"{CURL_PREFIX}{row.id}",
        kind=row.kind,
        name=row.name,
        description=row.description or "",
        handler_config=cfg,
        parameters=[],
        queue=cfg.get("queue") if isinstance(cfg, dict) else None,
        priority=cfg.get("priority") if isinstance(cfg, dict) else None,
    )


async def resolve_ref_async(db: AsyncSession, ref: str) -> ResolvedTask | None:
    if _looks_like_python_ref(ref):
        return _python_resolved(ref)
    cid = _curl_id_from_ref(ref)
    if cid:
        row = await db.get(Task, cid)
        if row:
            return _curl_resolved_from_row(row)
    return None


def resolve_ref_sync(session: Session, ref: str) -> ResolvedTask | None:
    if _looks_like_python_ref(ref):
        return _python_resolved(ref)
    cid = _curl_id_from_ref(ref)
    if cid:
        row = session.get(Task, cid)
        if row:
            return _curl_resolved_from_row(row)
    return None


def make_curl_ref(task_id: str) -> str:
    return f"{CURL_PREFIX}{task_id}"
