"""Behaviour: POST /ask returns citations or abstains, ACL-filtered, and records the request."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from bas_assistant.api.ask import get_retrieval_deps
from bas_assistant.db.activity import Request, RequestChunk, Thread, Usage, User
from bas_assistant.db.engine import Base, get_session
from bas_assistant.main import app
from bas_assistant.retrieval.pipeline import RetrievalDeps
from tests.fakes import (
    FakeEmbedder,
    FakeVectorStore,
    fake_reranker,
    make_chunk,
    make_document,
    make_parent,
)

pytestmark = pytest.mark.unit

_ACTIVITY_TABLES = [
    User.__table__,
    Thread.__table__,
    Request.__table__,
    RequestChunk.__table__,
    Usage.__table__,
]


@pytest.fixture
def db_session() -> Iterator[Session]:
    """An in-memory SQLite session with just the activity tables /ask writes to.

    Documents/parents/chunks use Postgres-only column types (ARRAY, JSONB,
    Vector, a computed TSVECTOR); the retrieval side is faked instead, so
    those tables are neither needed here nor creatable on SQLite.
    """
    # StaticPool: a plain sqlite:///:memory: engine hands out a fresh, empty
    # database per pooled connection, so create_all and every later query
    # must share the one connection this keeps alive for the engine's life.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    # `.__table__` is typed as the wider FromClause on the declarative base;
    # every mapped class here is a plain single Table, so this is safe.
    Base.metadata.create_all(engine, tables=_ACTIVITY_TABLES)  # type: ignore[arg-type]
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            User(email="support@test.demo", role="support"),
            User(email="engineer@test.demo", role="engineer"),
            User(email="admin@test.demo", role="admin"),
        ]
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    public_doc = make_document(acl_groups=["all"], title="Public Doc")
    public_parent = make_parent(public_doc, text="The O3 Sense power draw is 24 VDC, 1 W typical.")
    public_chunk = make_chunk(public_parent, text=public_parent.text, page=2)

    engineer_doc = make_document(acl_groups=["engineer"], title="Engineer Doc")
    engineer_parent = make_parent(engineer_doc, text="Engineer-only wiring diagram detail.")
    engineer_chunk = make_chunk(engineer_parent, text=engineer_parent.text, page=5)

    deps = RetrievalDeps(
        embedder=FakeEmbedder(),
        store=FakeVectorStore([public_chunk, engineer_chunk]),
        reranker=fake_reranker,
        rerank_threshold=0.1,
    )
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_retrieval_deps] = lambda: deps
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_ask_returns_citations_for_a_matching_question(client: TestClient) -> None:
    response = client.post(
        "/ask", json={"question": "power draw"}, headers={"X-Demo-Role": "support"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] is None
    assert body["abstained"] is False
    assert body["citations"][0]["page"] == 2


def test_ask_abstains_for_an_unmatched_question(client: TestClient) -> None:
    response = client.post(
        "/ask", json={"question": "unrelated gibberish xyzzy"}, headers={"X-Demo-Role": "support"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["abstained"] is True
    assert body["citations"] == []


def test_support_role_cannot_see_engineer_only_chunk(client: TestClient) -> None:
    response = client.post(
        "/ask", json={"question": "wiring diagram detail"}, headers={"X-Demo-Role": "support"}
    )

    assert response.json()["abstained"] is True


def test_engineer_role_sees_engineer_only_chunk(client: TestClient) -> None:
    response = client.post(
        "/ask", json={"question": "wiring diagram detail"}, headers={"X-Demo-Role": "engineer"}
    )

    assert response.json()["abstained"] is False


def test_missing_role_header_defaults_to_support(client: TestClient) -> None:
    response = client.post("/ask", json={"question": "power draw"})

    assert response.status_code == 200


def test_unknown_role_header_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/ask", json={"question": "power draw"}, headers={"X-Demo-Role": "hacker"}
    )

    assert response.status_code == 422


def test_ask_records_a_request_row(client: TestClient, db_session: Session) -> None:
    response = client.post(
        "/ask", json={"question": "power draw"}, headers={"X-Demo-Role": "support"}
    )
    request_id = uuid.UUID(response.json()["request_id"])

    saved = db_session.get(Request, request_id)
    assert saved is not None
    assert saved.decision == "retrieved"
    assert saved.role == "support"


def test_ask_never_logs_the_raw_question(client: TestClient, db_session: Session) -> None:
    response = client.post(
        "/ask",
        json={"question": "contact jason@example.com about the power draw"},
        headers={"X-Demo-Role": "support"},
    )
    request_id = uuid.UUID(response.json()["request_id"])

    saved = db_session.get(Request, request_id)
    assert saved is not None
    assert "jason@example.com" not in saved.question_redacted
    assert "[REDACTED]" in saved.question_redacted
