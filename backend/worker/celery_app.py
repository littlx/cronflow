"""Celery 应用 + redbeat 调度器配置。

- beat 进程使用 RedBeatScheduler: schedule 存 Redis, 支持动态增删 + leader election (无状态化)。
- worker 进程执行具体任务 (python_runner / curl_runner)。
"""
from __future__ import annotations

import os

from celery import Celery

from app.core.config import settings

# Celery 必须能序列化复杂对象时回退到 pickle; JSON 对我们的场景足够
os.environ.setdefault("CELERY_BROKER_URL", settings.redis_url)
os.environ.setdefault("CELERY_RESULT_BACKEND", settings.redis_url)

celery_app = Celery(
    "cronflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.task_runner"],
)

celery_app.conf.update(
    # 序列化
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # 鲁棒性默认
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # redbeat: schedule 存 Redis, 多 beat 实例自动选主
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.redis_url,
    beat_prefix="cronflow",
    # 防止 beat 重复发送已被禁用的任务
    redbeat_lock_key="cronflow:redbeat:lock",
    redbeat_lock_timeout=60,
)


def get_celery() -> Celery:
    return celery_app


# worker 进程启动时触发任务发现, 让 @register_task 注册表在 worker 内生效。
# (API 进程在 lifespan 里 discover; worker 是独立进程, 需单独触发)
from celery.signals import worker_process_init  # noqa: E402


@worker_process_init.connect
def _discover_on_worker_init(**kwargs):  # noqa: ANN001
    from app.registry.discover import discover_tasks
    discover_tasks()


# 兼容 solo 池 (不开子进程, worker_process_init 不触发): 模块导入时也 discover 一次
try:
    from app.registry.discover import discover_tasks
    discover_tasks()
except Exception as e:
    print(f"[celery_app] initial discover failed: {e}")
