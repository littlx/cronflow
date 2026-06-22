"""应用配置 — 通过环境变量注入，pydantic-settings 校验。"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 服务
    app_name: str = "CronFlow"
    host: str = "0.0.0.0"
    port: int = 8000

    # 数据库 (SQLite 单文件, WAL 模式; async 用 aiosqlite)
    database_url: str = "sqlite+aiosqlite:///./cronflow.db"

    # 执行层
    max_concurrency: int = 8          # executor 协程池并发上限
    task_retry_max: int = 3           # 最大重试次数 (瞬态故障)
    task_retry_backoff: float = 2.0   # 退避基数 (秒), 实际等待 = backoff * 2^(attempt-1)
    task_default_timeout: int = 60    # handler 默认超时 (秒)
    log_retention_days: int = 90      # 日志保留天数
    cache_retention_days: int = 30    # 缓存保留天数

    # 调度
    scheduler_tick_seconds: int = 5   # 调度循环扫描间隔

    # 认证 (首版预留, 不校验)
    secret_key: str = "change-me-in-production"
    auth_enabled: bool = False

    # 前端静态文件 (打包的 dist 目录, None = 不托管前端)
    static_dir: str | None = None

    # CORS (前端 dev server 时有用; 生产环境同域无需)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
