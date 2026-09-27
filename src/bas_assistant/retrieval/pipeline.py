"""Retrieval orchestration: embed, search, fuse, rerank, group, and decide abstain."""

from __future__ import annotations

import time
import uuid
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel

from bas_assistant.db.corpus import Chunk, Parent
from bas_assistant.observability.metrics import observe_retrieval
from bas_assistant.observability.tracing import tracer
from bas_assistant.retrieval.embeddings import EmbedBatch, EmbeddingProvider
from bas_assistant.retrieval.fusion import rrf
from bas_assistant.retrieval.rerank import Reranker
from bas_assistant.retrieval.store import VectorStore

# 20, not 15: golden row 13's answer (enteliWEB's browser list) fuses at rank 18; the reranker
# scores it best of all. MiniLM keeps 20 pairs under the 3 s budget (docs/adr/0003-reranker.md).
FUSED_TOP_N = 20
FINAL_TOP_N = 5
# Sections of one catalog sheet can fill all five places and leave the answer model one source
# to read; two per document leaves room for the others.
MAX_PASSAGES_PER_DOCUMENT = 2


class RetrievedChunk(BaseModel):
    """One reranked candidate, for the diagnostic `retrieved` view."""

    chunk_id: uuid.UUID
    document_title: str
    page: int
    score: float


class Citation(BaseModel):
    """One parent-level result, for the user-facing `citations` view."""

    # The best child chunk: the id the answer model cites the passage by.
    chunk_id: uuid.UUID
    document_title: str
    page: int
    source_url: str
    snippet: str
    # The whole parent, which is what the answer model reads.
    passage: str
    score: float


class Timings(BaseModel):
    """How long each retrieval stage took, in milliseconds."""

    embed_ms: int
    retrieval_ms: int
    rerank_ms: int
    total_ms: int


class RetrievalResult(BaseModel):
    """Everything /ask needs: citations, the broader candidate pool, and timings."""

    citations: list[Citation]
    retrieved: list[RetrievedChunk]
    abstained: bool
    timings: Timings
    embed_usage: EmbedBatch


@dataclass
class RetrievalDeps:
    """The retrieval pipeline's infrastructure, bundled for dependency injection."""

    embedder: EmbeddingProvider
    store: VectorStore
    reranker: Reranker
    rerank_threshold: float


def _fused_candidates(
    query: str, embedding: list[float], acl_groups: list[str], store: VectorStore
) -> list[Chunk]:
    """Vector + lexical candidates, RRF-fused, as full chunk rows in fused order."""
    vec_ranks = store.vector_candidates(embedding, acl_groups)
    lex_ranks = store.lexical_candidates(query, acl_groups)
    fused = rrf(vec_ranks, lex_ranks)
    top_ids = [
        chunk_id
        for chunk_id, _ in sorted(fused.items(), key=lambda item: item[1], reverse=True)[
            :FUSED_TOP_N
        ]
    ]
    by_id = {chunk.id: chunk for chunk in store.chunks(top_ids, acl_groups)}
    return [by_id[chunk_id] for chunk_id in top_ids if chunk_id in by_id]


def _rerank_text(chunk: Chunk) -> str:
    # Sibling products share sections word for word ("BACnet Building Controller (B-BC)"),
    # and a spec section rarely names its product; the title tells the cross-encoder which
    # product the chunk describes.
    return f"{chunk.document.title}\n{chunk.text}"


def _best_child_per_parent(
    chunks: list[Chunk], scores: list[float]
) -> dict[uuid.UUID, tuple[Chunk, float]]:
    """The highest-scoring child chunk for each parent, since a parent may have several."""
    best: dict[uuid.UUID, tuple[Chunk, float]] = {}
    for chunk, score in zip(chunks, scores, strict=True):
        current = best.get(chunk.parent_id)
        if current is None or score > current[1]:
            best[chunk.parent_id] = (chunk, score)
    return best


def _top_parents(
    best_per_parent: dict[uuid.UUID, tuple[Chunk, float]],
) -> list[tuple[Chunk, float]]:
    """The best-scoring parents, at most MAX_PASSAGES_PER_DOCUMENT from any one document."""
    per_document: Counter[uuid.UUID] = Counter()
    top: list[tuple[Chunk, float]] = []
    for chunk, score in sorted(best_per_parent.values(), key=lambda item: item[1], reverse=True):
        if per_document[chunk.document_id] == MAX_PASSAGES_PER_DOCUMENT:
            continue
        per_document[chunk.document_id] += 1
        top.append((chunk, score))
        if len(top) == FINAL_TOP_N:
            break
    return top


def _citation(parent: Parent, chunk: Chunk, score: float) -> Citation:
    return Citation(
        chunk_id=chunk.id,
        document_title=parent.document.title,
        page=chunk.page,
        source_url=parent.document.source_url,
        snippet=chunk.text[:300],
        passage=parent.text,
        score=score,
    )


def _select_citations(
    candidates: list[Chunk],
    scores: list[float],
    store: VectorStore,
    threshold: float,
    acl_groups: list[str],
) -> tuple[list[Citation], bool]:
    """Top-5 parents by best child score; abstain if even the best is below threshold."""
    top = _top_parents(_best_child_per_parent(candidates, scores))
    if not top or top[0][1] < threshold:
        return [], True
    parent_ids = [chunk.parent_id for chunk, _ in top]
    parents_by_id = {parent.id: parent for parent in store.parents(parent_ids, acl_groups)}
    citations = [_citation(parents_by_id[chunk.parent_id], chunk, score) for chunk, score in top]
    return citations, False


def _retrieved_view(candidates: list[Chunk], scores: list[float]) -> list[RetrievedChunk]:
    items = (
        RetrievedChunk(
            chunk_id=chunk.id, document_title=chunk.document.title, page=chunk.page, score=score
        )
        for chunk, score in zip(candidates, scores, strict=True)
    )
    return sorted(items, key=lambda item: item.score, reverse=True)


def retrieve(query: str, acl_groups: list[str], deps: RetrievalDeps) -> RetrievalResult:
    """Run the full hybrid-search-then-rerank pipeline for one question."""
    start = time.monotonic()
    embed_batch = deps.embedder.embed([query])
    embed_ms = int((time.monotonic() - start) * 1000)

    retrieval_start = time.monotonic()
    with tracer.start_as_current_span("retrieval.search") as span:
        candidates = _fused_candidates(query, embed_batch.vectors[0], acl_groups, deps.store)
        span.set_attribute("retrieval.candidates", len(candidates))
    retrieval_ms = int((time.monotonic() - retrieval_start) * 1000)

    rerank_start = time.monotonic()
    with tracer.start_as_current_span("retrieval.rerank") as span:
        # Skip the model call entirely on an empty pool — no ACL-visible chunk
        # matched at all — rather than trust the reranker to handle a 0-length batch.
        texts = [_rerank_text(chunk) for chunk in candidates]
        scores = deps.reranker(query, texts) if candidates else []
        span.set_attributes(
            {"rerank.pairs": len(scores), "rerank.top_score": max(scores, default=0)}
        )
    rerank_ms = int((time.monotonic() - rerank_start) * 1000)
    observe_retrieval(retrieval_ms, rerank_ms)

    citations, abstained = _select_citations(
        candidates, scores, deps.store, deps.rerank_threshold, acl_groups
    )
    total_ms = int((time.monotonic() - start) * 1000)
    return RetrievalResult(
        citations=citations,
        retrieved=_retrieved_view(candidates, scores),
        abstained=abstained,
        timings=Timings(
            embed_ms=embed_ms, retrieval_ms=retrieval_ms, rerank_ms=rerank_ms, total_ms=total_ms
        ),
        embed_usage=embed_batch,
    )
