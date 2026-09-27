"""Hybrid retrieval store: vector and lexical candidates, ACL-filtered, from Postgres.

VectorStore is one of the two interfaces CODING_STANDARDS.md allows even
though PgVectorStore is its only implementation — tests substitute an
in-memory fake (see tests/fakes.py) instead of hitting a real database.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy import ColumnElement, func, literal_column, select
from sqlalchemy.orm import Session, joinedload

from bas_assistant.db.corpus import Chunk, Document, Parent

CANDIDATE_LIMIT = 20


class VectorStore(Protocol):
    """Anything that can return ACL-filtered candidates and their parents."""

    def vector_candidates(
        self, embedding: list[float], acl_groups: list[str]
    ) -> dict[uuid.UUID, int]: ...

    def lexical_candidates(self, query: str, acl_groups: list[str]) -> dict[uuid.UUID, int]: ...

    def chunks(self, chunk_ids: list[uuid.UUID], acl_groups: list[str]) -> list[Chunk]: ...

    def parents(self, parent_ids: list[uuid.UUID], acl_groups: list[str]) -> list[Parent]: ...


def _or_tsquery(query: str) -> ColumnElement[Any]:  # func() return type is dynamic in SQLAlchemy
    """OR every distinct lexeme in the query together.

    websearch_to_tsquery ANDs plain terms — a natural-language question
    matches almost nothing that way — and, for a hyphenated term like
    "DAC-633PoE", joins the compound with its parts using <-> (phrase
    adjacency), which then requires that exact token sequence to recur
    verbatim in the chunk. Rewriting its output text (e.g. "&" to "|") only
    touches the AND case; ORing the query's own lexemes handles both, and
    the reranker is what supplies precision afterward.
    """
    lexemes = func.tsvector_to_array(func.to_tsvector("english", query))
    or_text = func.array_to_string(lexemes, " | ")
    return func.to_tsquery("english", or_text)


class PgVectorStore:
    """pgvector + tsvector hybrid search, ACL-filtered in SQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def vector_candidates(
        self, embedding: list[float], acl_groups: list[str]
    ) -> dict[uuid.UUID, int]:
        stmt = (
            select(Chunk.id)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.acl_groups.op("&&")(acl_groups))
            .order_by(Chunk.embedding.cosine_distance(embedding))
            .limit(CANDIDATE_LIMIT)
        )
        ids = self._session.scalars(stmt).all()
        return {chunk_id: rank for rank, chunk_id in enumerate(ids, start=1)}

    def lexical_candidates(self, query: str, acl_groups: list[str]) -> dict[uuid.UUID, int]:
        tsquery = _or_tsquery(query)
        # A short section ("## Power / 24 VDC (20 W max) ...") rarely names its product, so
        # the document title joins the chunk's words, weighted above them. Computed per
        # query: no index covers it, which is fine at a few thousand chunks.
        title = func.setweight(func.to_tsvector("english", Document.title), literal_column("'A'"))
        titled_tsv = title.op("||")(Chunk.tsv)
        stmt = (
            select(Chunk.id)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.acl_groups.op("&&")(acl_groups))
            .where(titled_tsv.op("@@")(tsquery))
            .order_by(func.ts_rank(titled_tsv, tsquery).desc())
            .limit(CANDIDATE_LIMIT)
        )
        ids = self._session.scalars(stmt).all()
        return {chunk_id: rank for rank, chunk_id in enumerate(ids, start=1)}

    def chunks(self, chunk_ids: list[uuid.UUID], acl_groups: list[str]) -> list[Chunk]:
        """Fetch chunks by id, ACL-filtered again here — never trust a caller's id list alone."""
        stmt = (
            select(Chunk)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.id.in_(chunk_ids))
            .where(Document.acl_groups.op("&&")(acl_groups))
            .options(joinedload(Chunk.document))
        )
        return list(self._session.scalars(stmt).unique())

    def parents(self, parent_ids: list[uuid.UUID], acl_groups: list[str]) -> list[Parent]:
        """Fetch parents by id, ACL-filtered again here — never trust a caller's id list alone."""
        stmt = (
            select(Parent)
            .join(Document, Parent.document_id == Document.id)
            .where(Parent.id.in_(parent_ids))
            .where(Document.acl_groups.op("&&")(acl_groups))
            .options(joinedload(Parent.document))
        )
        return list(self._session.scalars(stmt).unique())
