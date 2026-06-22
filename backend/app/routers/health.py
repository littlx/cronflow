"""健康检查路由。

注意: 不再注册 GET /, 否则会和 SPA fallback (FastAPI StaticFiles)
冲突。根路径在挂载了 SPA 时返回 index.html, 未挂载时返回 SPA fallback
内的 404 / 或 FastAPI 默认 404。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "cronflow"}