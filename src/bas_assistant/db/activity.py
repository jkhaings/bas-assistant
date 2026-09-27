"""Activity tables: users, threads, requests, usage, feedback, and evaluation.

See docs/ARCHITECTURE.md §2 for the design of record. Session A only writes to
``users`` (seeded), ``threads``, ``requests``, ``request_chunks``, and ``usage``
(stage=embed). The remaining tables are created now so later sessions never
need a migration that touches a table another session already depends on.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bas_assistant.db.engine import Base


class User(Base):
    """A person or service account. Demo roles stand in for SSO."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(20))  # support | engineer | admin | service
    team: Mapped[str] = mapped_column(String(50), default="default")
    api_key_hash: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Thread(Base):
    """A conversation. One per request in session A; reused across turns from B."""

    __tablename__ = "threads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Request(Base):
    """One row per /ask call."""

    __tablename__ = "requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20))
    question_redacted: Mapped[str] = mapped_column(Text)
    route: Mapped[str | None] = mapped_column(String(20))  # fast | strong — set from session B
    # retrieved | abstained in session A; answered | refused | paused | failed join in B/C
    decision: Mapped[str] = mapped_column(String(20))
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RequestChunk(Base):
    """A chunk retrieved for a request, and whether it made it into the answer."""

    __tablename__ = "request_chunks"

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Numeric(10, 6))
    used_in_answer: Mapped[bool] = mapped_column(Boolean, default=False)


class Usage(Base):
    """One row per model call: embeddings now, router/answer/judge from session B."""

    __tablename__ = "usage"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Nullable: ingestion embeds documents with no /ask request behind them.
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE")
    )
    stage: Mapped[str] = mapped_column(String(20))  # router | embed | answer | judge
    alias: Mapped[str] = mapped_column(String(20))  # fast | strong | embed
    model: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    usd: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    latency_ms: Mapped[int] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Feedback(Base):
    """The 'used without edits' letter metric, from session D's feedback endpoint."""

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    value: Mapped[str] = mapped_column(String(20))  # used_as_is | used_with_edits | not_used
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Flag(Base):
    """The 'sounded right but wasn't' letter metric, from session D's flag endpoint."""

    __tablename__ = "flags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    """A proposed-then-approved internal ticket, from session B's human gate."""

    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"))
    draft: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    approver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    jira_key: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Audit(Base):
    """Append-only log of every guard and gate decision."""

    __tablename__ = "audit"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE")
    )
    actor: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50))
    detail: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Budget(Base):
    """A spend limit: global daily cap, and per-user/team allowances from session B."""

    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(20))  # user | team | global
    period: Mapped[str] = mapped_column(String(20))  # daily | monthly
    usd_limit: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    tokens_limit: Mapped[int | None] = mapped_column(Integer)


class EvalRun(Base):
    """One row per golden-set or red-team run, from session C."""

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20), default="golden")  # golden | redteam
    corpus_version: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(20))
    scores: Mapped[dict[str, object]] = mapped_column(JSONB)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
