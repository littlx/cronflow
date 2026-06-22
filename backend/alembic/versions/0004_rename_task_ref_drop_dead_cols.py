"""rename task_logs.task_id → task_ref + drop dead columns from job_schedules

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-18

1) task_logs.task_id 命名误导(实际存的是 ref, 包括 'curl:xxx'), 重命名为 task_ref
   并重建索引。
2) job_schedules 的 next_run_time / redbeat_key 是「双写但无人写也无人读」的死字段,
   真相源是 redbeat (entry.due_at + 固定前缀 key), API 已改为运行时从 redbeat 取,
   故直接 DROP, 同步删掉只为这两列准备的复合索引。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) task_logs.task_id → task_ref
    op.drop_index("ix_task_logs_task_id", table_name="task_logs")
    op.alter_column("task_logs", "task_id", new_column_name="task_ref")
    op.create_index("ix_task_logs_task_ref", "task_logs", ["task_ref"])

    # 2) drop double-write 死字段
    op.drop_index("ix_schedules_enabled_next_run", table_name="job_schedules")
    op.drop_column("job_schedules", "next_run_time")
    op.drop_column("job_schedules", "redbeat_key")
    op.create_index("ix_schedules_enabled", "job_schedules", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_schedules_enabled", table_name="job_schedules")
    op.add_column(
        "job_schedules",
        sa.Column("redbeat_key", sa.String(255), nullable=True),
    )
    op.add_column(
        "job_schedules",
        sa.Column("next_run_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_schedules_enabled_next_run",
        "job_schedules",
        ["enabled", "next_run_time"],
    )

    op.drop_index("ix_task_logs_task_ref", table_name="task_logs")
    op.alter_column("task_logs", "task_ref", new_column_name="task_id")
    op.create_index("ix_task_logs_task_id", "task_logs", ["task_id"])
