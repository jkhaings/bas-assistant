"""Deterministic fakes for unit tests: no network, no docker, no model download.

Substitutes for the three pluggable interfaces the retrieval pipeline takes:
EmbeddingProvider, VectorStore, and Reranker.
"""

from __future__ import annotations

import hashlib
import math
import uuid
from decimal import Decimal

from bas_assistant.db.corpus import Chunk, Document, Parent
from bas_assistant.retrieval.embeddings import EmbedBatch

EMBED_DIM = 1536


def _hash_vector(text: str) -> list[float]:
    """A deterministic, L2-normalised pseudo-embedding derived from a hash of the text."""
    digest = hashlib.sha256(text.encode()).digest()
    raw = [float(digest[i % len(digest)]) - 128.0 for i in range(EMBED_DIM)]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [v / norm for v in raw]


class FakeEmbedder:
    """A deterministic embedder: the same text always gives the same vector."""

    model = "fake-embedder"

    def embed(self, texts: list[str]) -> EmbedBatch:
        return EmbedBatch(
            vectors=[_hash_vector(text) for text in texts],
            input_tokens=sum(len(text.split()) for text in texts),
            usd=Decimal("0"),
            latency_ms=0,
        )


def fake_reranker(query: str, passages: list[str]) -> list[float]:
    """Score by word overlap with the query — deterministic, no model download."""
    query_words = set(query.lower().split())
    return [len(query_words & set(p.lower().split())) / (len(query_words) or 1) for p in passages]


def _visible(chunk: Chunk, acl_groups: list[str]) -> bool:
    return bool(set(chunk.document.acl_groups) & set(acl_groups))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


class FakeVectorStore:
    """An in-memory VectorStore: cosine similarity and substring match, no SQL."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = {chunk.id: chunk for chunk in chunks}

    def vector_candidates(
        self, embedding: list[float], acl_groups: list[str]
    ) -> dict[uuid.UUID, int]:
        visible = [c for c in self._chunks.values() if _visible(c, acl_groups)]
        scored = sorted(visible, key=lambda c: _cosine(embedding, c.embedding), reverse=True)
        return {chunk.id: rank for rank, chunk in enumerate(scored[:20], start=1)}

    def lexical_candidates(self, query: str, acl_groups: list[str]) -> dict[uuid.UUID, int]:
        terms = query.lower().split()
        visible = [c for c in self._chunks.values() if _visible(c, acl_groups)]
        matching = [c for c in visible if any(t in c.text.lower() for t in terms)]
        scored = sorted(
            matching, key=lambda c: sum(c.text.lower().count(t) for t in terms), reverse=True
        )
        return {chunk.id: rank for rank, chunk in enumerate(scored[:20], start=1)}

    def chunks(self, chunk_ids: list[uuid.UUID], acl_groups: list[str]) -> list[Chunk]:
        return [
            self._chunks[chunk_id]
            for chunk_id in chunk_ids
            if chunk_id in self._chunks and _visible(self._chunks[chunk_id], acl_groups)
        ]

    def parents(self, parent_ids: list[uuid.UUID], acl_groups: list[str]) -> list[Parent]:
        seen: dict[uuid.UUID, Parent] = {}
        for chunk in self._chunks.values():
            visible_parent = chunk.parent_id in parent_ids and _visible(chunk, acl_groups)
            if visible_parent and chunk.parent_id not in seen:
                seen[chunk.parent_id] = chunk.parent
        return list(seen.values())


def make_document(*, acl_groups: list[str] | None = None, title: str = "Test Doc") -> Document:
    """A minimal, unpersisted Document for building small test corpora."""
    return Document(
        id=uuid.uuid4(),
        title=title,
        source_url=f"https://example.com/{title}",
        source_type="pdf",
        product="Test Product",
        doc_type="catalog",
        acl_groups=acl_groups or ["all"],
        content_hash="hash",
        parse_quality="docling",
    )


def make_parent(document: Document, *, text: str = "parent text") -> Parent:
    """A minimal, unpersisted Parent linked back to its document."""
    parent = Parent(id=uuid.uuid4(), document_id=document.id, page_start=1, page_end=1, text=text)
    parent.document = document
    return parent


def make_chunk(parent: Parent, *, text: str = "chunk text", page: int = 1) -> Chunk:
    """A minimal, unpersisted Chunk linked back to its parent and document."""
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=parent.document_id,
        parent_id=parent.id,
        page=page,
        position=0,
        text=text,
        embedding=_hash_vector(text),
    )
    chunk.document = parent.document
    chunk.parent = parent
    return chunk
