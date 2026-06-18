"""健康检查路由。"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/")
async def root():
    return {"service": "cronflow-v2", "docs": "/docs", "health": "/health"}


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "cronflow-v2"}
