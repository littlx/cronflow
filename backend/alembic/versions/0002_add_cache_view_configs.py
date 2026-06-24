"""add cache_view_configs — 缓存数据的表格列展示配置

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cache_view_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_collection", sa.String(255), nullable=False, unique=True),
        sa.Column("row_path", sa.String(255), nullable=False, server_default=""),
        sa.Column("columns", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_cache_view_configs_collection",
        "cache_view_configs",
        ["target_collection"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_cache_view_configs_collection", table_name="cache_view_configs")
    op.drop_table("cache_view_configs")
