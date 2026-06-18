"""FastAPI 公共依赖。"""
from __future__ import annotations

from app.core.security import CurrentUser, get_current_user

__all__ = ["CurrentUser", "get_current_user"]
