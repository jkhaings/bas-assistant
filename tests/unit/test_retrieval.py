"""Behaviour: the reranker judges each chunk together with the title of its document."""

import pytest

from bas_assistant.retrieval.pipeline import RetrievalDeps, retrieve
from tests.fakes import (
    FakeEmbedder,
    FakeVectorStore,
    fake_reranker,
    make_chunk,
    make_document,
    make_parent,
)

pytestmark = pytest.mark.unit

# Sibling catalog sheets share this section word for word; only the title says whose it is.
_SHARED_SECTION = "## Specifications\n\nBACnet Device Profile BACnet Building Controller (B-BC)"


def test_a_section_that_never_names_its_product_scores_higher_under_the_asked_product() -> None:
    chunks = [
        make_chunk(
            make_parent(make_document(title=title), text=_SHARED_SECTION), text=_SHARED_SECTION
        )
        for title in ("Red5-FIELD-V100", "Red5-PLUS-1146")
    ]
    deps = RetrievalDeps(
        embedder=FakeEmbedder(),
        store=FakeVectorStore(chunks),
        reranker=fake_reranker,
        rerank_threshold=0.1,
    )

    result = retrieve("What BACnet profile does the Red5-PLUS-1146 support?", ["all"], deps)

    scores = {citation.document_title: citation.score for citation in result.citations}
    assert scores["Red5-PLUS-1146"] > scores["Red5-FIELD-V100"]


def test_one_document_fills_at_most_two_of_the_five_places() -> None:
    crowded = make_document(title="Red5-PLUS-1146")
    other = make_document(title="Red5-FIELD-V100")
    chunks = [
        make_chunk(make_parent(crowded, text=text), text=text)
        for text in (
            "bacnet device profile one",
            "bacnet device profile two",
            "bacnet device profile",
        )
    ]
    chunks.append(make_chunk(make_parent(other, text="bacnet profile"), text="bacnet profile"))
    deps = RetrievalDeps(
        embedder=FakeEmbedder(),
        store=FakeVectorStore(chunks),
        reranker=fake_reranker,
        rerank_threshold=0.1,
    )

    result = retrieve("bacnet device profile", ["all"], deps)

    titles = [citation.document_title for citation in result.citations]
    assert titles.count("Red5-PLUS-1146") == 2
    assert "Red5-FIELD-V100" in titles
