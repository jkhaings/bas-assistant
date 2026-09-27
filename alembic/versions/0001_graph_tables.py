"""Tables for the agent graph: users, threads, requests, usage, tickets, audit.

Revision ID: 0001
Revises:
Create Date: 2026-09-26
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[UUID]:
    return sa.Column("id", sa.Uuid(), primary_key=True)


def _created_at() -> sa.Column[datetime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def _users() -> None:
    users = op.create_table(
        "users",
        _id(),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("api_key_hash", sa.String(128)),
        _created_at(),
    )
    # The three "View as" demo users. Session A seeds the service account.
    op.bulk_insert(
        users,
        [
            {"id": uuid4(), "email": f"{role}@demo.local", "role": role}
            for role in ("support", "engineer", "admin")
        ],
    )


def _threads_and_requests() -> None:
    op.create_table(
        "threads",
        _id(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        _created_at(),
    )
    op.create_table(
        "requests",
        _id(),
        sa.Column("thread_id", sa.Uuid(), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("question_redacted", sa.Text(), nullable=False),
        sa.Column("route", sa.String(16)),
        sa.Column("decision", sa.String(16)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("retrieval_ms", sa.Integer()),
        sa.Column("rerank_ms", sa.Integer()),
        _created_at(),
    )


def _usage() -> None:
    op.create_table(
        "usage",
        _id(),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("requests.id"), index=True),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("alias", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_tokens", sa.Integer(), nullable=False),
        sa.Column("usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        _created_at(),
    )
    op.create_index("ix_usage_created_at", "usage", ["created_at"])


def _tickets_and_audit() -> None:
    op.create_table(
        "tickets",
        _id(),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("draft", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("approver_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("jira_key", sa.String(32)),
        _created_at(),
    )
    op.create_table(
        "audit",
        _id(),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("requests.id")),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        _created_at(),
    )


def upgrade() -> None:
    _users()
    _threads_and_requests()
    _usage()
    _tickets_and_audit()


def downgrade() -> None:
    for table in ("audit", "tickets", "usage", "requests", "threads", "users"):
        op.drop_table(table)
