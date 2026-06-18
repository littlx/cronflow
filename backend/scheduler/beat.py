"""celery-redbeat 调度 entry 增删 helper。

redbeat 把 schedule 存在 Redis 中, beat 进程通过 leader election 选主后按 tick 扫描到期任务
并 send_task。API 层增删调度时, 同步写 DB + 通过本模块增删 RedBeatSchedulerEntry, 实现
"DB 为真相源 + redbeat 负责无状态分发"。

schedule 对象用 celery 原生的 schedule(timedelta) / crontab, redbeat 兼容这些标准类型。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from celery.schedules import crontab, schedule as celery_schedule

# task name 映射
_PYTHON_TASK = "worker.run_python_task"
_CURL_TASK = "worker.run_curl_task"


def _entry_name(schedule_id: int) -> str:
    return f"cronflow:schedule:{schedule_id}"


def _entry_key(entry_name: str) -> str:
    """redbeat 在 Redis 中存储 entry 的 key。

    redbeat 内部存储格式为: '<redbeat_prefix>:<entry_name>', 默认 redbeat_prefix='redbeat'。
    所以实际 key = 'redbeat:cronflow:schedule:1'。
    """
    return f"redbeat:{entry_name}"


def _build_schedule(trigger_type: str, trigger_args: dict[str, Any]):
    """从 trigger_args 构造 celery schedule 对象 (redbeat 兼容)。"""
    args = {k: v for k, v in (trigger_args or {}).items() if v is not None and v != ""}
    if trigger_type == "interval":
        seconds = 0
        matched = False
        for unit, factor in (("seconds", 1), ("minutes", 60), ("hours", 3600), ("days", 86400)):
            if unit in args:
                seconds = int(args[unit]) * factor
                matched = True
                break
        if not matched or seconds <= 0:
            seconds = 300  # 默认 5 分钟
        return celery_schedule(timedelta(seconds=seconds))
    elif trigger_type == "cron":
        return crontab(
            minute=args.get("minute", "*"),
            hour=args.get("hour", "*"),
            day_of_month=args.get("day_of_month", args.get("day", "*")),
            month_of_year=args.get("month_of_year", args.get("month", "*")),
            day_of_week=args.get("day_of_week", "*"),
        )
    else:
        raise ValueError(f"不支持的触发类型: {trigger_type}")


def _build_kwargs(task_type: str, task_id: str, trigger_type: str,
                  task_args: dict, schedule_id: int) -> dict:
    if task_type == "curl":
        return {"task_id": task_id, "trigger_type": trigger_type, "schedule_id": schedule_id}
    return {
        "task_id": task_id,
        "trigger_type": trigger_type,
        "task_args": task_args or {},
        "schedule_id": schedule_id,
    }


def _save_entry(entry_name: str, task_name: str, schedule, kwargs: dict, enabled: bool) -> None:
    from redbeat import RedBeatSchedulerEntry
    from worker.celery_app import celery_app

    entry = RedBeatSchedulerEntry(
        name=entry_name,
        task=task_name,
        schedule=schedule,
        kwargs=kwargs,
        app=celery_app,
    )
    entry.save()
    if not enabled:
        # 重新取出置 disabled
        entry = RedBeatSchedulerEntry.from_key(_entry_key(entry_name), app=celery_app)
        entry.enabled = False
        entry.save()


def upsert_schedule_entry(
    schedule_id: int,
    task_id: str,
    name: str,
    task_type: str,
    trigger_type: str,
    trigger_args: dict[str, Any],
    task_args: dict[str, Any] | None = None,
    enabled: bool = True,
) -> str:
    """新增或更新一个 redbeat 调度 entry。返回 entry name。"""
    entry_name = _entry_name(schedule_id)
    task_name = _CURL_TASK if task_type == "curl" else _PYTHON_TASK
    schedule = _build_schedule(trigger_type, trigger_args)
    kwargs = _build_kwargs(task_type, task_id, trigger_type, task_args or {}, schedule_id)
    try:
        _save_entry(entry_name, task_name, schedule, kwargs, enabled)
        return entry_name
    except Exception as e:
        print(f"[beat] upsert entry {entry_name} failed: {e}")
        raise


def delete_schedule_entry(schedule_id: int) -> None:
    """删除一个 redbeat 调度 entry。不存在则忽略。"""
    try:
        from redbeat import RedBeatSchedulerEntry
        from worker.celery_app import celery_app
        entry = RedBeatSchedulerEntry.from_key(_entry_key(_entry_name(schedule_id)), app=celery_app)
        entry.delete()
    except Exception:
        pass


def set_schedule_enabled(schedule_id: int, enabled: bool) -> None:
    """启用/禁用一个 redbeat 调度 entry。"""
    try:
        from redbeat import RedBeatSchedulerEntry
        from worker.celery_app import celery_app
        entry = RedBeatSchedulerEntry.from_key(_entry_key(_entry_name(schedule_id)), app=celery_app)
        entry.enabled = enabled
        entry.save()
    except Exception as e:
        print(f"[beat] toggle failed: {e}")
