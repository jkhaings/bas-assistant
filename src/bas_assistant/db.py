"""Tables this service reads and writes. Columns follow docs/ARCHITECTURE.md section 2."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Engine,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    Uuid,
    create_engine,
    make_url,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

# JSONB on Postgres; plain JSON lets the unit tests run on SQLite.
_JSON = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(UTC)


def _created_at() -> Column[datetime]:
    return Column("created_at", DateTime(timezone=True), nullable=False, default=_now)


users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True, default=uuid4),
    Column("email", String(255), nullable=False, unique=True),
    Column("role", String(32), nullable=False),
    Column("api_key_hash", String(128)),
    _created_at(),
)

threads = Table(
    "threads",
    metadata,
    Column("id", Uuid, primary_key=True, default=uuid4),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False),
    _created_at(),
)

requests = Table(
    "requests",
    metadata,
    Column("id", Uuid, primary_key=True, default=uuid4),
    Column("thread_id", Uuid, ForeignKey("threads.id"), nullable=False),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("role", String(32), nullable=False),
    Column("question_redacted", Text, nullable=False),
    Column("route", String(16)),
    Column("decision", String(16)),
    Column("latency_ms", Integer),
    Column("retrieval_ms", Integer),
    Column("rerank_ms", Integer),
    _created_at(),
)

usage = Table(
    "usage",
    metadata,
    Column("id", Uuid, primary_key=True, default=uuid4),
    # Null for calls outside a request, such as ingest embeddings.
    Column("request_id", Uuid, ForeignKey("requests.id"), index=True),
    Column("stage", String(16), nullable=False),
    Column("alias", String(32), nullable=False),
    Column("model", String(128), nullable=False),
    Column("provider", String(32), nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cached_tokens", Integer, nullable=False),
    Column("usd", Numeric(12, 6), nullable=False),
    Column("latency_ms", Integer, nullable=False),
    Column("cache_hit", Boolean, nullable=False),
    _created_at(),
)
# The daily USD cap sums today's rows.
Index("ix_usage_created_at", usage.c.created_at)

tickets = Table(
    "tickets",
    metadata,
    Column("id", Uuid, primary_key=True, default=uuid4),
    Column("request_id", Uuid, ForeignKey("requests.id"), nullable=False),
    Column("draft", _JSON, nullable=False),
    Column("status", String(16), nullable=False),
    Column("approver_id", Uuid, ForeignKey("users.id")),
    Column("jira_key", String(32)),
    _created_at(),
)

audit = Table(
    "audit",
    metadata,
    Column("id", Uuid, primary_key=True, default=uuid4),
    Column("request_id", Uuid, ForeignKey("requests.id")),
    Column("actor", String(64), nullable=False),
    Column("action", String(64), nullable=False),
    Column("detail", _JSON, nullable=False),
    _created_at(),
)


def create_db_engine(database_url: str) -> Engine:
    return create_engine(
        make_url(database_url).set(drivername="postgresql+psycopg"), pool_pre_ping=True
    )
