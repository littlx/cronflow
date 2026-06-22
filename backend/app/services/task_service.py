"""统一 task service — python (注册表) + curl (DB) 任务的 CRUD。

python 任务: 只读, 来自 @register_task 注册表。
curl   任务: 表单创建, 入 tasks 表 (kind='curl')。
返回视图统一为 {ref, kind, name, description, handler_config, parameters, queue, priority}。
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
        "queue": t.get("queue"),
        "priority": t.get("priority"),
        "module": t.get("module"),
    }


def _curl_view(row: Task) -> dict:
    cfg = row.handler_config or {}
    return {
        "ref": make_curl_ref(row.id),
        "kind": row.kind,
        "name": row.name,
        "description": row.description or "",
        "handler_config": cfg,
        "parameters": [],
        "queue": cfg.get("queue") if isinstance(cfg, dict) else None,
        "priority": cfg.get("priority") if isinstance(cfg, dict) else None,
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
            "queue": r.queue, "priority": r.priority,
        }
    # curl
    row = await db.get(Task, ref[len(CURL_PREFIX):]) if ref.startswith(CURL_PREFIX) else None
    return _curl_view(row) if row else None


async def create_curl_task(db: AsyncSession, payload: dict) -> dict:
    """创建一个 curl 任务 (kind='curl')。
    payload: {name, description?, handler_config: {url, method, headers, data, handler_type, target_collection, queue?, priority?}}
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


# ---- 调度时的 task_args 预校验 ----

def validate_task_args(resolved: ResolvedTask, task_args: dict[str, Any]) -> list[str]:
    """对照 resolved.parameters 检查 task_args, 返回错误描述列表 (空表示通过)。

    仅校验 python 任务 — curl 任务参数从 handler_config 取, 不依赖 task_args。
    校验项:
    - required 参数缺失
    - 类型与签名不一致 (int/float/bool/str)
    """
    errors: list[str] = []
    if resolved.kind != "python":
        return errors
    for p in resolved.parameters:
        name = p["name"]
        if name not in task_args:
            if p.get("required"):
                errors.append(f"参数 {name} 是必填项")
            continue
        val = task_args[name]
        if val is None or val == "":
            if p.get("required"):
                errors.append(f"参数 {name} 不能为空")
            continue
        ptype = (p.get("type") or "str").lower()
        if ptype in ("int", "integer"):
            if isinstance(val, bool) or not _is_int_like(val):
                errors.append(f"参数 {name} 必须是整数")
        elif ptype in ("float", "number"):
            if not _is_num_like(val):
                errors.append(f"参数 {name} 必须是数字")
        elif ptype in ("bool", "boolean"):
            if not isinstance(val, (bool, int)) and str(val).lower() not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
                errors.append(f"参数 {name} 必须是布尔值")
    return errors


def _is_int_like(v: Any) -> bool:
    if isinstance(v, int) and not isinstance(v, bool):
        return True
    try:
        int(str(v))
        return True
    except (TypeError, ValueError):
        return False


def _is_num_like(v: Any) -> bool:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return True
    try:
        float(str(v))
        return True
    except (TypeError, ValueError):
        return False
