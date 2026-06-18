"""unify task model — drop curl_tasks, create tasks; schedules drop task_type rename task_id→task_ref

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 新建统一 tasks 表 (kind=curl 入库; python 不入库)
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(64), primary_key=True),       # uuid hex
        sa.Column("kind", sa.String(32), nullable=False),        # 'curl' | 未来 'shell'/'sql'/...
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("handler_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tasks_kind", "tasks", ["kind"])

    # 2. 旧 curl_tasks 废弃 (v2 无数据, 直接 drop)
    op.drop_index("ix_curl_tasks_target_collection", table_name="curl_tasks")
    op.drop_table("curl_tasks")

    # 3. schedules 调整: 删 task_type, 重命名 task_id -> task_ref (语义改变)
    op.drop_column("job_schedules", "task_type")
    op.alter_column("job_schedules", "task_id", new_column_name="task_ref")
    op.drop_index("ix_job_schedules_task_id", table_name="job_schedules")
    op.create_index("ix_schedules_task_ref", "job_schedules", ["task_ref"])


def downgrade() -> None:
    op.drop_index("ix_schedules_task_ref", table_name="job_schedules")
    op.create_index("ix_job_schedules_task_id", "job_schedules", ["task_ref"])
    op.alter_column("job_schedules", "task_ref", new_column_name="task_id")
    op.add_column("job_schedules", sa.Column("task_type", sa.String(50), nullable=False, server_default="python"))

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

    op.drop_index("ix_tasks_kind", table_name="tasks")
    op.drop_table("tasks")
