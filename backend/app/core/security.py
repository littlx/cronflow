"""认证接口 — 首版预留。

所有受保护路由 Depends(get_current_user)。首版 auth_enabled=False 直接放行, 返回固定 admin。
后续接 JWT + RBAC 时只改本文件, 不破坏路由签名。
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    username: str
    role: str = "admin"


# TODO(auth): 接入 JWT 校验 + RBAC。首版放行。
async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentUser:
    if not settings.auth_enabled:
        return CurrentUser(username="admin", role="admin")

    # --- 以下为未来 JWT 实现占位 ---
    if creds is None or creds.credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证",
        )
    # TODO: 解析 JWT, 校验签名/过期, 返回真实用户
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证未实现",
    )
