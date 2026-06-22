"""initial schema — 六张核心表

Revision ID: 0001
Revises:
Create Date: 2026-06-22

表:
- tasks              : kind=curl 等表单创建任务入库; python 不入库 (JSON handler_config)
- job_schedules      : task_ref 字符串 + JSON trigger_args/task_args + next_run_time 真相源
- task_logs          : task_ref 命名, 含 attempt 列 (重试新建行)
- crawled_data_cache : curl handler 写入的 JSON 文档
- idempotency_keys   : 幂等去重 (INSERT ON CONFLICT, 跨方言)
- notification_configs / notification_logs : 通知渠道配置 + 发送记录
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- tasks: 统一任务表 (curl 入库; python 注册表内存态不入库) ----
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("handler_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_tasks_kind", "tasks", ["kind"])

    # ---- job_schedules: 调度配置 (next_run_time 真相源) ----
    op.create_table(
        "job_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_ref", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_args", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("task_args", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("next_run_time", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_schedules_task_ref", "job_schedules", ["task_ref"])
    op.create_index("ix_schedules_enabled", "job_schedules", ["enabled"])
    op.create_index("ix_schedules_next_run_time", "job_schedules", ["next_run_time"])

    # ---- task_logs: 执行日志 (attempt 列支持重试多行) ----
    op.create_table(
        "task_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_ref", sa.String(255), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_task_logs_task_ref", "task_logs", ["task_ref"])
    op.create_index("ix_task_logs_schedule_id", "task_logs", ["schedule_id"])
    op.create_index("ix_task_logs_status", "task_logs", ["status"])
    op.create_index("ix_task_logs_started_at", "task_logs", ["started_at"])

    # ---- crawled_data_cache: curl handler 写入的 JSON 文档 ----
    op.create_table(
        "crawled_data_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_collection", sa.String(255), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_cache_collection_created", "crawled_data_cache", ["target_collection", "created_at"])

    # ---- idempotency_keys: 幂等去重 ----
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(255), nullable=False, unique=True),
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_idempotency_keys_key", "idempotency_keys", ["key"])

    # ---- notification_configs: 通知渠道配置 ----
    op.create_table(
        "notification_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("events", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.String(1), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_notification_configs_channel", "notification_configs", ["channel"])

    # ---- notification_logs: 通知发送记录 ----
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("task_log_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_notification_logs_config_id", "notification_logs", ["config_id"])
    op.create_index("ix_notification_logs_task_log_id", "notification_logs", ["task_log_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_logs_task_log_id", table_name="notification_logs")
    op.drop_index("ix_notification_logs_config_id", table_name="notification_logs")
    op.drop_table("notification_logs")

    op.drop_index("ix_notification_configs_channel", table_name="notification_configs")
    op.drop_table("notification_configs")

    op.drop_index("ix_idempotency_keys_key", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")

    op.drop_index("ix_cache_collection_created", table_name="crawled_data_cache")
    op.drop_table("crawled_data_cache")

    op.drop_index("ix_task_logs_started_at", table_name="task_logs")
    op.drop_index("ix_task_logs_status", table_name="task_logs")
    op.drop_index("ix_task_logs_schedule_id", table_name="task_logs")
    op.drop_index("ix_task_logs_task_ref", table_name="task_logs")
    op.drop_table("task_logs")

    op.drop_index("ix_schedules_next_run_time", table_name="job_schedules")
    op.drop_index("ix_schedules_enabled", table_name="job_schedules")
    op.drop_index("ix_schedules_task_ref", table_name="job_schedules")
    op.drop_table("job_schedules")

    op.drop_index("ix_tasks_kind", table_name="tasks")
    op.drop_table("tasks")
