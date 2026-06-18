"""Redis 客户端。

- async client: 供 API 层使用 (stats 计数器、幂等锁)
- sync client: 供 Celery worker 使用
"""
from __future__ import annotations

import redis.asyncio as aioredis
import redis

from app.core.config import settings


# API 层异步客户端
async_redis = aioredis.from_url(settings.redis_url, decode_responses=True)


# Worker 层同步客户端
sync_redis = redis.from_url(settings.redis_url, decode_responses=True)


def get_redis_stats_key(metric: str) -> str:
    """stats 计数器 key 命名。metric ∈ {total, success, failed, running}"""
    return f"cronflow:stats:{metric}"
