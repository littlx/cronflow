"""统一 task service — python (注册表) + curl (DB) 任务的 CRUD。

python 任务: 只读, 来自 @register_task 注册表。
curl   任务: 表单创建, 入 tasks 表 (kind='curl')。
返回视图统一为 {ref, kind, name, description, handler_config, parameters}。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.registry import list_tasks as list_python_tasks
from app.services.ref_resolver import CURL_PREFIX, ResolvedTask, make_curl_ref


def _python_view(t: dict) -> dict:
    return {
        "ref": t["id"],
        "kind": "python",
        "name": t["name"],
        "description": t["description"],
        "handler_config": {},
        "parameters": t["parameters"],
        "module": t.get("module"),
    }


def _curl_view(row: Task) -> dict:
    return {
        "ref": make_curl_ref(row.id),
        "kind": row.kind,
        "name": row.name,
        "description": row.description or "",
        "handler_config": row.handler_config or {},
        "parameters": [],
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_all_tasks(db: AsyncSession, kind: str | None = None) -> list[dict]:
    """列出所有任务, 可按 kind 过滤。python 来自注册表, 其他 kind 来自 tasks 表。"""
    out: list[dict] = []
    if kind in (None, "python"):
        out.extend(_python_view(t) for t in list_python_tasks())
    if kind in (None,) or (kind and kind != "python"):
        stmt = select(Task)
        if kind:
            stmt = stmt.where(Task.kind == kind)
        rows = (await db.execute(stmt.order_by(Task.created_at))).scalars().all()
        out.extend(_curl_view(r) for r in rows)
    return out


async def get_task_view(db: AsyncSession, ref: str) -> dict | None:
    from app.services.ref_resolver import resolve_ref_async
    r = await resolve_ref_async(db, ref)
    if not r:
        return None
    if r.kind == "python":
        return {
            "ref": r.ref, "kind": "python", "name": r.name,
            "description": r.description, "handler_config": {},
            "parameters": r.parameters,
        }
    # curl
    row = await db.get(Task, ref[len(CURL_PREFIX):]) if ref.startswith(CURL_PREFIX) else None
    return _curl_view(row) if row else None


async def create_curl_task(db: AsyncSession, payload: dict) -> dict:
    """创建一个 curl 任务 (kind='curl')。
    payload: {name, description?, handler_config: {url, method, headers, data, handler_type, target_collection}}
    """
    task = Task(
        id=uuid.uuid4().hex,
        kind="curl",
        name=payload["name"],
        description=payload.get("description"),
        handler_config=payload.get("handler_config") or {},
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return _curl_view(task)


async def update_curl_task(db: AsyncSession, task_id: str, payload: dict) -> dict | None:
    row = await db.get(Task, task_id)
    if not row:
        return None
    if "name" in payload and payload["name"] is not None:
        row.name = payload["name"]
    if "description" in payload:
        row.description = payload["description"]
    if "handler_config" in payload and payload["handler_config"] is not None:
        row.handler_config = payload["handler_config"]
    await db.commit()
    await db.refresh(row)
    return _curl_view(row)


async def delete_curl_task(db: AsyncSession, task_id: str) -> bool:
    row = await db.get(Task, task_id)
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    return True
