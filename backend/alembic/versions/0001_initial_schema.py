"""initial schema — 四张核心表 (合并自原 0001-0004)

Revision ID: 0001
Revises:
Create Date: 2026-06-18

开发阶段一次性建好最终形态:
- tasks       : kind=curl 入库; python 不入库 (JSONB handler_config)
- job_schedules: task_ref 字符串 + JSONB trigger_args/task_args, 不双写
                 next_run_time / redbeat_key (真相源 redbeat)
- task_logs   : task_ref 命名, 含 attempt 列 (重试新建行)
- crawled_data_cache: JSONB document 缓存
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- tasks: 统一任务表 (curl 入库; python 注册表内存态不入库) ----
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(64), primary_key=True),         # uuid hex
        sa.Column("kind", sa.String(32), nullable=False),          # 'curl' | 未来 'shell' / 'sql' / ...
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "handler_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tasks_kind", "tasks", ["kind"])

    # ---- job_schedules: 调度配置 (next_run_time / redbeat_key 不双写, 真相源在 redbeat) ----
    op.create_table(
        "job_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_ref", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),   # interval | cron
        sa.Column(
            "trigger_args",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "task_args",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_schedules_task_ref", "job_schedules", ["task_ref"])
    op.create_index("ix_schedules_enabled", "job_schedules", ["enabled"])

    # ---- task_logs: 执行日志 (attempt 列支持重试多行) ----
    op.create_table(
        "task_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_ref", sa.String(255), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),   # manual | interval | cron
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),         # running | success | failed
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_task_logs_task_ref", "task_logs", ["task_ref"])
    op.create_index("ix_task_logs_schedule_id", "task_logs", ["schedule_id"])
    op.create_index("ix_task_logs_status", "task_logs", ["status"])
    op.create_index("ix_task_logs_started_at", "task_logs", ["started_at"])

    # ---- crawled_data_cache: curl handler 写入的 JSONB 文档 ----
    op.create_table(
        "crawled_data_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_collection", sa.String(255), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_cache_collection_created",
        "crawled_data_cache",
        ["target_collection", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cache_collection_created", table_name="crawled_data_cache")
    op.drop_table("crawled_data_cache")

    op.drop_index("ix_task_logs_started_at", table_name="task_logs")
    op.drop_index("ix_task_logs_status", table_name="task_logs")
    op.drop_index("ix_task_logs_schedule_id", table_name="task_logs")
    op.drop_index("ix_task_logs_task_ref", table_name="task_logs")
    op.drop_table("task_logs")

    op.drop_index("ix_schedules_enabled", table_name="job_schedules")
    op.drop_index("ix_schedules_task_ref", table_name="job_schedules")
    op.drop_table("job_schedules")

    op.drop_index("ix_tasks_kind", table_name="tasks")
    op.drop_table("tasks")
