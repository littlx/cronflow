"""task_logs add attempt column

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-18

为支持「每次重试写一行新日志」, task_logs 增加 attempt 字段
(1=首次执行, 2=第一次重试, ...). 历史数据默认填 1。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_logs",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("task_logs", "attempt")
