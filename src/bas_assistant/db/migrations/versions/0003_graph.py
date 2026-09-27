"""Agent graph columns: request timings, in-flight nulls, and the daily-cap index.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("requests", sa.Column("retrieval_ms", sa.Integer))
    op.add_column("requests", sa.Column("rerank_ms", sa.Integer))
    # The graph writes the request row before it runs and fills these in when it closes.
    op.alter_column("requests", "decision", existing_type=sa.String(20), nullable=True)
    op.alter_column("requests", "latency_ms", existing_type=sa.Integer, nullable=True)
    op.create_index("ix_usage_created_at", "usage", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_usage_created_at", table_name="usage")
    op.alter_column("requests", "latency_ms", existing_type=sa.Integer, nullable=False)
    op.alter_column("requests", "decision", existing_type=sa.String(20), nullable=False)
    op.drop_column("requests", "rerank_ms")
    op.drop_column("requests", "retrieval_ms")
