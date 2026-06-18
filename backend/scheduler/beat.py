"""celery-redbeat 调度 entry 增删 helper。

统一发 task 'worker.run_task', kwargs 携带 task_ref, 由 worker 端解析 ref → kind → handler。
不再分发 python / curl 两种 task name。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from celery.schedules import crontab, schedule as celery_schedule

_RUN_TASK = "worker.run_task"


def _entry_name(schedule_id: int) -> str:
    return f"cronflow:schedule:{schedule_id}"


def _entry_key(entry_name: str) -> str:
    """redbeat 在 Redis 中存储 entry 的 key: 固定前缀 'redbeat:'。"""
    return f"redbeat:{entry_name}"


def _build_schedule(trigger_type: str, trigger_args: dict[str, Any]):
    args = {k: v for k, v in (trigger_args or {}).items() if v is not None and v != ""}
    if trigger_type == "interval":
        seconds = 0
        for unit, factor in (("seconds", 1), ("minutes", 60), ("hours", 3600), ("days", 86400)):
            if unit in args:
                seconds = int(args[unit]) * factor
                break
        if seconds <= 0:
            seconds = 300
        return celery_schedule(timedelta(seconds=seconds))
    if trigger_type == "cron":
        return crontab(
            minute=args.get("minute", "*"),
            hour=args.get("hour", "*"),
            day_of_month=args.get("day_of_month", args.get("day", "*")),
            month_of_year=args.get("month_of_year", args.get("month", "*")),
            day_of_week=args.get("day_of_week", "*"),
        )
    raise ValueError(f"不支持的触发类型: {trigger_type}")


def upsert_schedule_entry(
    schedule_id: int,
    task_ref: str,
    trigger_type: str,
    trigger_args: dict[str, Any],
    task_args: dict[str, Any] | None = None,
    enabled: bool = True,
) -> str:
    """新增/更新一个 redbeat entry, 返回 entry name。"""
    from redbeat import RedBeatSchedulerEntry
    from worker.celery_app import celery_app

    entry_name = _entry_name(schedule_id)
    schedule = _build_schedule(trigger_type, trigger_args)
    kwargs = {
        "task_ref": task_ref,
        "trigger_type": trigger_type,
        "task_args": task_args or {},
        "schedule_id": schedule_id,
    }

    entry = RedBeatSchedulerEntry(
        name=entry_name,
        task=_RUN_TASK,
        schedule=schedule,
        kwargs=kwargs,
        app=celery_app,
    )
    entry.save()
    if not enabled:
        entry = RedBeatSchedulerEntry.from_key(_entry_key(entry_name), app=celery_app)
        entry.enabled = False
        entry.save()
    return entry_name


def delete_schedule_entry(schedule_id: int) -> None:
    try:
        from redbeat import RedBeatSchedulerEntry
        from worker.celery_app import celery_app
        entry = RedBeatSchedulerEntry.from_key(_entry_key(_entry_name(schedule_id)), app=celery_app)
        entry.delete()
    except Exception:
        pass


def set_schedule_enabled(schedule_id: int, enabled: bool) -> None:
    try:
        from redbeat import RedBeatSchedulerEntry
        from worker.celery_app import celery_app
        entry = RedBeatSchedulerEntry.from_key(_entry_key(_entry_name(schedule_id)), app=celery_app)
        entry.enabled = enabled
        entry.save()
    except Exception as e:
        print(f"[beat] toggle failed: {e}")
