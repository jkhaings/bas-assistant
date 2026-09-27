"""The graph's retrieve node, backed by session A's hybrid search over the ingested corpus."""

from functools import partial

from sqlalchemy.orm import Session

from bas_assistant.agent.state import Passage, Retrieval
from bas_assistant.db.engine import get_engine
from bas_assistant.llm.gateway import Usage
from bas_assistant.retrieval.embeddings import EmbedBatch, EmbeddingProvider
from bas_assistant.retrieval.pipeline import RetrievalDeps, RetrievalResult, retrieve
from bas_assistant.retrieval.rerank import rerank
from bas_assistant.retrieval.store import PgVectorStore
from bas_assistant.settings import Settings


def _embed_usage(batch: EmbedBatch, requested_model: str) -> Usage:
    provider, model = batch.provider_and_model(requested_model)
    return Usage(
        alias="embed",
        model=model,
        provider=provider,
        input_tokens=batch.input_tokens,
        output_tokens=0,
        cached_tokens=0,
        usd=batch.usd,
        latency_ms=batch.latency_ms,
    )


def to_retrieval(result: RetrievalResult, embed_model: str) -> Retrieval:
    """Top-5 parents become the passages the answer model reads; abstain means none."""
    passages = [
        Passage(
            chunk_id=str(citation.chunk_id),
            document_title=citation.document_title,
            page=citation.page,
            source_url=citation.source_url,
            text=citation.passage,
            score=citation.score,
        )
        for citation in ([] if result.abstained else result.citations)
    ]
    return Retrieval(
        passages=passages,
        retrieval_ms=result.timings.retrieval_ms,
        rerank_ms=result.timings.rerank_ms,
        embed=_embed_usage(result.embed_usage, embed_model),
    )


def search_corpus(
    embedder: EmbeddingProvider, settings: Settings, question: str, acl_groups: list[str]
) -> Retrieval:
    with Session(get_engine()) as session:
        result = retrieve(
            question,
            acl_groups,
            RetrievalDeps(
                embedder=embedder,
                store=PgVectorStore(session),
                reranker=partial(rerank, settings.rerank_model),
                rerank_threshold=settings.rerank_threshold,
            ),
        )
    return to_retrieval(result, embedder.model)
