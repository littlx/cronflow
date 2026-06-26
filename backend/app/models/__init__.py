"""ORM 模型聚合导入 — alembic/env.py 与 db 初始化时统一注册到 Base.metadata。"""
from __future__ import annotations

from app.models.cache import CrawledDataCache
from app.models.cache_view_config import CacheViewConfig
from app.models.dashboard_config import DashboardConfig
from app.models.idempotency import IdempotencyKey
from app.models.notification import NotificationConfig, NotificationLog
from app.models.schedule import JobSchedule
from app.models.task import Task
from app.models.task_log import TaskLog

__all__ = [
    "Task",
    "JobSchedule",
    "TaskLog",
    "CrawledDataCache",
    "CacheViewConfig",
    "DashboardConfig",
    "IdempotencyKey",
    "NotificationConfig",
    "NotificationLog",
]
