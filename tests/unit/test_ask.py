"""Behaviour: /ask routes, answers with citations, abstains, and respects spend limits."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert

from bas_assistant.db.activity import Usage
from bas_assistant.runtime import AppRuntime
from tests.graph_fakes import (
    CHUNK_1,
    SOURCE_URL,
    FakeProxy,
    FakeRetriever,
    answer_json,
    ask,
    make_client,
)

pytestmark = pytest.mark.unit


def test_answer_cites_the_retrieved_passage(client: TestClient) -> None:
    body = ask(client, "How much power does the sample controller draw?").json()

    assert body["decision"] == "answered"
    assert body["answer"] == "The sample controller draws 4 W at 24 VAC."
    assert body["citations"] == [
        {
            "chunk_id": CHUNK_1,
            "document_title": "Sample Controller Catalog Sheet",
            "page": 2,
            "source_url": SOURCE_URL,
            "snippet": "The sample controller draws 4 W at 24 VAC.",
        }
    ]


def test_simple_question_is_answered_by_the_fast_alias(client: TestClient) -> None:
    body = ask(client, "Supply voltage of the sample controller?").json()

    assert (body["route"], body["model"]) == ("fast", "gpt-4o-mini")


def test_complex_question_is_answered_by_the_strong_alias(
    client: TestClient, proxy: FakeProxy
) -> None:
    proxy.complexity = "complex"

    body = ask(client, "Compare the sample controller with its predecessor").json()

    assert (body["route"], body["model"]) == ("strong", "claude-sonnet-4-6")


def test_no_passages_abstains_without_an_answer_call(
    client: TestClient, proxy: FakeProxy, retriever: FakeRetriever
) -> None:
    retriever.passages = []

    body = ask(client, "What is the capital of France?").json()

    assert body["decision"] == "abstained"
    assert body["citations"] == []
    assert "couldn't find this in the documentation" in body["answer"]
    assert proxy.answer_calls() == []


def test_retrieval_uses_the_role_acl_groups(client: TestClient, retriever: FakeRetriever) -> None:
    ask(client, "q1", role="support")
    ask(client, "q2", role="engineer")

    assert retriever.seen_acl_groups == [["all"], ["all", "engineer"]]


def test_missing_role_header_is_read_as_support(
    client: TestClient, retriever: FakeRetriever
) -> None:
    assert client.post("/ask", json={"question": "hi"}).status_code == 200
    assert retriever.seen_acl_groups == [["all"]]


def test_unknown_role_is_rejected(client: TestClient) -> None:
    response = client.post("/ask", json={"question": "hi"}, headers={"X-Demo-Role": "root"})
    assert response.status_code == 422


def test_daily_cap_reached_returns_503_with_reset_time(
    client: TestClient, engine: Engine, proxy: FakeProxy
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(Usage).values(
                stage="answer",
                alias="strong",
                model="m",
                provider="p",
                input_tokens=0,
                output_tokens=0,
                cached_tokens=0,
                usd=Decimal(3),
                latency_ms=0,
                cache_hit=False,
            )
        )

    response = ask(client, "anything")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["reason"] == "daily_budget_reached"
    assert datetime.fromisoformat(detail["resets_at"]) > datetime.now(UTC)
    assert proxy.calls == []


def test_used_up_allowance_returns_429_with_retry_after(runtime: AppRuntime) -> None:
    client = make_client(replace(runtime, user_daily_questions=1))

    assert ask(client, "first").status_code == 200
    response = ask(client, "second")

    assert response.status_code == 429
    assert response.json()["detail"]["reason"] == "daily_allowance_used"
    assert 0 < int(response.headers["Retry-After"]) <= 86400


def test_model_outage_fails_the_request_and_refunds_the_allowance(
    runtime: AppRuntime, proxy: FakeProxy
) -> None:
    client = make_client(replace(runtime, user_daily_questions=1))
    proxy.down = {"fast", "strong"}

    failed = ask(client, "first")
    proxy.down = set()
    retried = ask(client, "first, again")

    assert failed.status_code == 503
    assert failed.json()["detail"]["reason"] == "model_unavailable"
    assert retried.status_code == 200


def test_router_output_that_breaks_the_schema_routes_to_strong(
    client: TestClient, proxy: FakeProxy
) -> None:
    proxy.route_reply = "not json"

    body = ask(client, "Power draw?").json()

    assert (body["route"], body["model"]) == ("strong", "claude-sonnet-4-6")


def test_router_topic_with_a_link_is_not_echoed_when_abstaining(
    client: TestClient, proxy: FakeProxy, retriever: FakeRetriever
) -> None:
    retriever.passages = []
    proxy.route_reply = '{"complexity": "simple", "topic": "see https://evil.example.net"}'

    body = ask(client, "anything").json()

    assert body["decision"] == "abstained"
    assert "evil" not in body["answer"]


def test_rejected_answers_still_use_up_the_allowance(runtime: AppRuntime, proxy: FakeProxy) -> None:
    client = make_client(replace(runtime, user_daily_questions=1))
    fabricated = answer_json(citations=("c999",))
    proxy.answers = [fabricated, fabricated]

    assert ask(client, "first").json()["decision"] == "failed"
    assert ask(client, "second").status_code == 429


def test_cached_answers_do_not_use_up_the_allowance(runtime: AppRuntime) -> None:
    client = make_client(replace(runtime, user_daily_questions=1))

    first = ask(client, "Power draw?")
    repeats = [ask(client, "Power draw?") for _ in range(3)]
    new_question = ask(client, "Wiring?")

    assert first.status_code == 200
    assert [r.json()["cache_hit"] for r in repeats] == [True, True, True]
    assert new_question.status_code == 429
