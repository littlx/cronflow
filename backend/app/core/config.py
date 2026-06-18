"""应用配置 — 通过环境变量注入，pydantic-settings 校验。"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 服务
    app_name: str = "CronFlow v2"
    api_prefix: str = "/api"
    host: str = "0.0.0.0"
    port: int = 8000

    # 数据库 (async sqlalchemy 使用 asyncpg; 同步 worker/alembic 使用 psycopg2)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cronflow_v2"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/cronflow_v2"

    # Redis (broker + result + redbeat + pub/sub + 锁 + stats 计数器)
    redis_url: str = "redis://localhost:6379/0"

    # 认证 (首版预留, 不校验)
    secret_key: str = "change-me-in-production"
    auth_enabled: bool = False

    # 执行层
    task_time_limit: int = 600          # 硬超时 (秒)
    task_soft_time_limit: int = 540     # 软超时 (秒)
    task_retry_max: int = 3
    log_retention_days: int = 90

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
