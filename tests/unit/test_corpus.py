"""Behaviour: session A's retrieval result becomes the passages the answer model reads."""

import uuid
from decimal import Decimal

import pytest

from bas_assistant.agent.corpus import to_retrieval
from bas_assistant.retrieval.embeddings import EmbedBatch
from bas_assistant.retrieval.pipeline import Citation, RetrievalResult, Timings

pytestmark = pytest.mark.unit

_CHUNK = uuid.uuid4()


def _result(
    *, abstained: bool, deployment: str = "openai/text-embedding-3-small"
) -> RetrievalResult:
    citation = Citation(
        chunk_id=_CHUNK,
        document_title="eBM-800 Catalog Sheet",
        page=2,
        source_url="https://example.com/eBM-800.pdf",
        snippet="24 VAC/VDC",
        passage="Power: 24 VAC/VDC, 50/60 Hz @ 5 VA.",
        score=0.92,
    )
    return RetrievalResult(
        citations=[citation],
        retrieved=[],
        abstained=abstained,
        timings=Timings(embed_ms=5, retrieval_ms=11, rerank_ms=22, total_ms=40),
        embed_usage=EmbedBatch(
            vectors=[[0.0]],
            input_tokens=9,
            usd=Decimal("0.00000018"),
            latency_ms=5,
            deployment=deployment,
        ),
    )


def test_each_citation_becomes_a_passage_with_the_whole_parent_text() -> None:
    retrieval = to_retrieval(_result(abstained=False), "embed")

    assert [(p.chunk_id, p.text, p.page) for p in retrieval.passages] == [
        (str(_CHUNK), "Power: 24 VAC/VDC, 50/60 Hz @ 5 VA.", 2)
    ]
    assert (retrieval.retrieval_ms, retrieval.rerank_ms) == (11, 22)


def test_a_retrieval_abstain_gives_the_graph_no_passages() -> None:
    assert to_retrieval(_result(abstained=True), "embed").passages == []


def test_query_embedding_cost_is_reported_with_the_deployment_that_served_it() -> None:
    embed = to_retrieval(_result(abstained=False), "embed").embed

    assert embed is not None
    assert (embed.alias, embed.provider, embed.model) == (
        "embed",
        "openai",
        "text-embedding-3-small",
    )
    assert (embed.input_tokens, embed.usd) == (9, Decimal("0.00000018"))
