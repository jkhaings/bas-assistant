"""Enable pgvector, create the corpus tables, seed demo users.

Revision ID: 0001
Revises:
Create Date: 2026-09-26

"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1536


def _create_documents_table() -> None:
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False, unique=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("product", sa.String(100), nullable=False),
        sa.Column("doc_type", sa.String(50), nullable=False),
        sa.Column("acl_groups", sa.ARRAY(sa.String), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("parse_quality", sa.String(20), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def _create_parents_table() -> None:
    op.create_table(
        "parents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_start", sa.Integer, nullable=False),
        sa.Column("page_end", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
    )


def _create_chunks_table() -> None:
    op.create_table(
        "chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("parents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page", sa.Integer, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column(
            "tsv",
            TSVECTOR,
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=False,
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    op.create_index(
        "ix_chunks_embedding",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def _create_users_table_and_seed() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("team", sa.String(50), nullable=False, server_default="default"),
        sa.Column("api_key_hash", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    users = sa.table(
        "users",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("email", sa.String),
        sa.column("role", sa.String),
    )
    op.bulk_insert(
        users,
        [
            {"id": uuid.uuid4(), "email": "support@bas-assistant.demo", "role": "support"},
            {"id": uuid.uuid4(), "email": "engineer@bas-assistant.demo", "role": "engineer"},
            {"id": uuid.uuid4(), "email": "admin@bas-assistant.demo", "role": "admin"},
            {"id": uuid.uuid4(), "email": "service@bas-assistant.demo", "role": "service"},
        ],
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _create_documents_table()
    _create_parents_table()
    _create_chunks_table()
    _create_users_table_and_seed()


def downgrade() -> None:
    op.drop_table("users")
    op.drop_index("ix_chunks_embedding", table_name="chunks")
    op.drop_index("ix_chunks_tsv", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("parents")
    op.drop_table("documents")
    op.execute("DROP EXTENSION IF EXISTS vector")
