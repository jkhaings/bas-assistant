"""Create the remaining activity tables: threads, requests, usage, and evaluation.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIMESTAMP = sa.Column(
    "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
)


def _create_threads_table() -> None:
    op.create_table(
        "threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        _TIMESTAMP.copy(),
    )


def _create_requests_table() -> None:
    op.create_table(
        "requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("question_redacted", sa.Text, nullable=False),
        sa.Column("route", sa.String(20), nullable=True),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        _TIMESTAMP.copy(),
    )


def _create_request_chunks_table() -> None:
    op.create_table(
        "request_chunks",
        sa.Column(
            "request_id",
            UUID(as_uuid=True),
            sa.ForeignKey("requests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "chunk_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("score", sa.Numeric(10, 6), nullable=False),
        sa.Column("used_in_answer", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def _create_usage_table() -> None:
    op.create_table(
        "usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id", UUID(as_uuid=True), sa.ForeignKey("requests.id", ondelete="CASCADE")
        ),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("alias", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("cache_hit", sa.Boolean, nullable=False, server_default=sa.false()),
        _TIMESTAMP.copy(),
    )


def _create_feedback_table() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            UUID(as_uuid=True),
            sa.ForeignKey("requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("value", sa.String(20), nullable=False),
        _TIMESTAMP.copy(),
    )


def _create_flags_table() -> None:
    op.create_table(
        "flags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            UUID(as_uuid=True),
            sa.ForeignKey("requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reviewer_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        _TIMESTAMP.copy(),
    )


def _create_tickets_table() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            UUID(as_uuid=True),
            sa.ForeignKey("requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("draft", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("approver_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("jira_key", sa.String(50), nullable=True),
        _TIMESTAMP.copy(),
    )


def _create_audit_table() -> None:
    op.create_table(
        "audit",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id", UUID(as_uuid=True), sa.ForeignKey("requests.id", ondelete="CASCADE")
        ),
        sa.Column("actor", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("detail", JSONB, nullable=False, server_default="{}"),
        _TIMESTAMP.copy(),
    )


def _create_budgets_table() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("usd_limit", sa.Numeric(10, 2), nullable=False),
        sa.Column("tokens_limit", sa.Integer, nullable=True),
    )


def _create_eval_runs_table() -> None:
    op.create_table(
        "eval_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="golden"),
        sa.Column("corpus_version", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("scores", JSONB, nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=False),
        _TIMESTAMP.copy(),
    )


def upgrade() -> None:
    _create_threads_table()
    _create_requests_table()
    _create_request_chunks_table()
    _create_usage_table()
    _create_feedback_table()
    _create_flags_table()
    _create_tickets_table()
    _create_audit_table()
    _create_budgets_table()
    _create_eval_runs_table()


def downgrade() -> None:
    for table in (
        "eval_runs",
        "budgets",
        "audit",
        "tickets",
        "flags",
        "feedback",
        "usage",
        "request_chunks",
        "requests",
        "threads",
    ):
        op.drop_table(table)
