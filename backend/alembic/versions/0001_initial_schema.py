"""initial schema — 四张核心表

Revision ID: 0001
Revises:
Create Date: 2026-06-18
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
    # job_schedules
    op.create_table(
        "job_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False, server_default="python"),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_args", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("task_args", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("redbeat_key", sa.String(255), nullable=True),
        sa.Column("next_run_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_job_schedules_task_id", "job_schedules", ["task_id"])
    op.create_index("ix_schedules_enabled_next_run", "job_schedules", ["enabled", "next_run_time"])

    # task_logs
    op.create_table(
        "task_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.String(255), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_task_logs_task_id", "task_logs", ["task_id"])
    op.create_index("ix_task_logs_schedule_id", "task_logs", ["schedule_id"])
    op.create_index("ix_task_logs_status", "task_logs", ["status"])
    op.create_index("ix_task_logs_started_at", "task_logs", ["started_at"])

    # curl_tasks
    op.create_table(
        "curl_tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("handler_type", sa.String(50), server_default="PURE_JSON"),
        sa.Column("target_collection", sa.String(255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("method", sa.String(10), server_default="GET"),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(50), server_default="idle"),
        sa.Column("last_run_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_result", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_curl_tasks_target_collection", "curl_tasks", ["target_collection"])

    # crawled_data_cache
    op.create_table(
        "crawled_data_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_collection", sa.String(255), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_cache_collection_created", "crawled_data_cache", ["target_collection", "created_at"])


def downgrade() -> None:
    op.drop_table("crawled_data_cache")
    op.drop_table("curl_tasks")
    op.drop_table("task_logs")
    op.drop_table("job_schedules")
