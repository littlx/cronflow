"""Prometheus 指标定义。

label 命名沿用模型字段: task_ref / status / trigger_type, 与 task_logs 表一致。
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# 任务执行计数 (按状态)
TASK_TOTAL = Counter(
    "cronflow_task_total", "任务执行总数",
    ["task_ref", "status", "trigger_type"],
)

TASK_DURATION = Histogram(
    "cronflow_task_duration_seconds", "任务执行耗时(秒)",
    ["task_ref"],
)

ACTIVE_SCHEDULES = Gauge("cronflow_active_schedules", "启用的调度数")
REGISTERED_TASKS = Gauge("cronflow_registered_tasks", "已注册任务数")
