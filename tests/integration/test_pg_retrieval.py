"""Integration behaviour: real Postgres — ACL filter, lexical search, ingest idempotency.

Runs against bas_test (see `make test-int`), which alembic has already migrated
and seeded with the four demo users.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from bas_assistant.api.ask import _create_request, _record_result
from bas_assistant.api.roles import Role
from bas_assistant.db.activity import Request, Usage
from bas_assistant.db.corpus import Chunk, Document, Parent, current_corpus_version
from bas_assistant.ingest.crawl import RawSource
from bas_assistant.ingest.pipeline import run_ingest
from bas_assistant.retrieval.pipeline import RetrievalResult, Timings
from bas_assistant.retrieval.store import PgVectorStore
from bas_assistant.settings import Settings
from tests.fakes import FakeEmbedder

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(Settings().database_url)
    with Session(engine) as db_session:
        yield db_session


def _add_document(
    session: Session, *, acl_groups: list[str], text: str, title: str = "Integration Test Doc"
) -> tuple[Document, Chunk]:
    embedder = FakeEmbedder()
    document = Document(
        title=title,
        source_url=f"https://example.com/{uuid.uuid4()}",
        source_type="pdf",
        product="Test Product",
        doc_type="catalog",
        acl_groups=acl_groups,
        content_hash=str(uuid.uuid4()),
        parse_quality="docling",
    )
    session.add(document)
    session.flush()
    parent = Parent(document_id=document.id, page_start=1, page_end=1, text=text)
    session.add(parent)
    session.flush()
    chunk = Chunk(
        document_id=document.id,
        parent_id=parent.id,
        page=1,
        position=0,
        text=text,
        embedding=embedder.embed([text]).vectors[0],
    )
    session.add(chunk)
    session.commit()
    return document, chunk


def test_lexical_search_finds_a_section_whose_product_is_named_only_in_the_title(
    session: Session,
) -> None:
    product = f"Zx{uuid.uuid4().hex[:8]}"
    titled, titled_chunk = _add_document(
        session, acl_groups=["all"], text="## Power\n\n24 VDC (20 W max)", title=product
    )
    untitled, untitled_chunk = _add_document(
        session, acl_groups=["all"], text="Power supply power rating and power wiring."
    )
    try:
        hits = PgVectorStore(session).lexical_candidates(f"power draw of the {product}", ["all"])

        assert titled_chunk.id in hits
        assert hits[titled_chunk.id] < hits.get(untitled_chunk.id, len(hits) + 1)
    finally:
        session.delete(titled)
        session.delete(untitled)
        session.commit()


def test_support_role_cannot_see_engineer_only_chunk(session: Session) -> None:
    document, chunk = _add_document(session, acl_groups=["engineer"], text="secret wiring detail")
    try:
        store = PgVectorStore(session)
        query_vector = FakeEmbedder().embed(["secret wiring detail"]).vectors[0]

        support_hits = store.vector_candidates(query_vector, acl_groups=["all"])
        engineer_hits = store.vector_candidates(query_vector, acl_groups=["all", "engineer"])

        assert chunk.id not in support_hits
        assert chunk.id in engineer_hits
    finally:
        session.delete(document)
        session.commit()


def test_lexical_search_finds_an_exact_model_number(session: Session) -> None:
    document, chunk = _add_document(
        session, acl_groups=["all"], text="The DAC-633PoE controller supports Modbus RTU."
    )
    try:
        hits = PgVectorStore(session).lexical_candidates("DAC-633PoE", ["all"])
        assert chunk.id in hits
    finally:
        session.delete(document)
        session.commit()


def test_reingesting_unchanged_content_is_skipped(session: Session) -> None:
    url = f"https://example.com/{uuid.uuid4()}"
    source = RawSource(
        url=url,
        filename="test-page",
        product="Test",
        doc_type="page",
        acl_groups=["all"],
        source_type="page",
        content=b"<html><body><main><p>Stable test content.</p></main></body></html>",
    )
    try:
        report1 = run_ingest(session, [source], FakeEmbedder())
        report2 = run_ingest(session, [source], FakeEmbedder())

        assert report1.failed == 0
        assert report1.ingested == 1
        assert report2.ingested == 0
        assert report2.skipped == 1
    finally:
        doc = session.scalars(select(Document).where(Document.source_url == url)).one_or_none()
        if doc is not None:
            session.delete(doc)
            session.commit()


def test_changed_content_replaces_the_chunks(session: Session) -> None:
    url = f"https://example.com/{uuid.uuid4()}"
    embedder = FakeEmbedder()
    original = RawSource(
        url=url,
        filename="test-page",
        product="Test",
        doc_type="page",
        acl_groups=["all"],
        source_type="page",
        content=b"<html><body><main><p>Original content here.</p></main></body></html>",
    )
    try:
        run_ingest(session, [original], embedder)
        first_doc = session.scalars(select(Document).where(Document.source_url == url)).one()
        original_chunk_ids = {
            c.id for c in session.scalars(select(Chunk).where(Chunk.document_id == first_doc.id))
        }

        updated = original.model_copy(
            update={
                "content": b"<html><body><main><p>Brand new different text.</p></main></body></html>"
            }
        )
        report2 = run_ingest(session, [updated], embedder)

        assert report2.updated == 1
        second_doc = session.scalars(select(Document).where(Document.source_url == url)).one()
        new_chunks = list(session.scalars(select(Chunk).where(Chunk.document_id == second_doc.id)))
        assert {c.id for c in new_chunks}.isdisjoint(original_chunk_ids)
        assert any("Brand new" in c.text for c in new_chunks)
    finally:
        doc = session.scalars(select(Document).where(Document.source_url == url)).one_or_none()
        if doc is not None:
            session.delete(doc)
            session.commit()


def test_ask_recording_writes_requests_and_usage_against_real_schema(session: Session) -> None:
    result = RetrievalResult(
        citations=[],
        retrieved=[],
        abstained=True,
        timings=Timings(embed_ms=1, retrieval_ms=1, rerank_ms=0, total_ms=2),
        embed_usage=FakeEmbedder().embed(["test question"]),
    )
    request = _create_request(session, Role.SUPPORT, "test question", "abstained", 2)
    _record_result(session, request, result, "fake-embedder")

    saved = session.get(Request, request.id)
    assert saved is not None
    assert saved.decision == "abstained"
    usage_rows = list(session.scalars(select(Usage).where(Usage.request_id == request.id)))
    assert len(usage_rows) == 1
    assert usage_rows[0].stage == "embed"


def test_corpus_version_moves_when_a_document_is_added_or_replaced(session: Session) -> None:
    engine = create_engine(Settings().database_url)
    before = current_corpus_version(engine, "2")
    added, _ = _add_document(session, acl_groups=["all"], text="Version check, first cut.")
    after_add = current_corpus_version(engine, "2")
    # An ingest replaces a changed document by deleting it and inserting the new version.
    session.delete(added)
    session.commit()
    replaced, _ = _add_document(session, acl_groups=["all"], text="Version check, second cut.")
    after_replace = current_corpus_version(engine, "2")
    unchanged = current_corpus_version(engine, "2")
    engine.dispose()
    session.delete(replaced)
    session.commit()

    assert len({before, after_add, after_replace}) == 3
    assert unchanged == after_replace
    assert after_replace.startswith("2.")
