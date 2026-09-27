"""Behaviour: receipts add up the proxy's per-call costs; repeat questions cost nothing."""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from bas_assistant.db.activity import RequestChunk
from bas_assistant.llm.gateway import Usage
from tests.graph_fakes import (
    CHUNK_1,
    CHUNK_2,
    COST_USD,
    INPUT_TOKENS,
    OUTPUT_TOKENS,
    FakeProxy,
    FakeRetriever,
    ask,
)

pytestmark = pytest.mark.unit


def test_receipt_totals_match_the_costs_litellm_reported(client: TestClient) -> None:
    request_id = ask(client, "Power draw?").json()["request_id"]

    receipt = client.get(f"/requests/{request_id}/receipt").json()

    assert [call["stage"] for call in receipt["calls"]] == ["router", "answer"]
    assert receipt["usd"] == pytest.approx(2 * float(COST_USD["fast"]))
    assert receipt["input_tokens"] == 2 * INPUT_TOKENS
    assert receipt["output_tokens"] == 2 * OUTPUT_TOKENS
    assert (receipt["route"], receipt["model"], receipt["cache_hit"]) == (
        "fast",
        "gpt-4o-mini",
        False,
    )
    assert (receipt["retrieval_ms"], receipt["rerank_ms"]) == (12, 34)
    assert receipt["total_ms"] >= 0


def test_strong_route_receipt_shows_router_and_answer_costs_separately(
    client: TestClient, proxy: FakeProxy
) -> None:
    proxy.complexity = "complex"
    request_id = ask(client, "Compare A and B").json()["request_id"]

    calls = client.get(f"/requests/{request_id}/receipt").json()["calls"]

    assert [(c["stage"], c["alias"], c["usd"]) for c in calls] == [
        ("router", "fast", float(COST_USD["fast"])),
        ("answer", "strong", float(COST_USD["strong"])),
    ]


def test_repeat_question_is_served_from_cache_at_zero_cost(
    client: TestClient, proxy: FakeProxy
) -> None:
    first = ask(client, "How much power does it draw?").json()
    calls_after_first = len(proxy.calls)

    second = ask(client, "  how much power does it DRAW? ").json()
    receipt = client.get(f"/requests/{second['request_id']}/receipt").json()

    assert second["cache_hit"] is True
    assert second["answer"] == first["answer"]
    assert second["citations"] == first["citations"]
    assert len(proxy.calls) == calls_after_first
    assert (receipt["cache_hit"], receipt["usd"], receipt["model"]) == (True, 0.0, "cache")


def test_cache_is_per_role(client: TestClient, proxy: FakeProxy) -> None:
    ask(client, "Power draw?", role="support")
    calls_after_first = len(proxy.calls)

    body = ask(client, "Power draw?", role="engineer").json()

    assert body["cache_hit"] is False
    assert len(proxy.calls) > calls_after_first


def test_follow_up_in_a_thread_is_not_served_from_cache(
    client: TestClient, proxy: FakeProxy
) -> None:
    ask(client, "Power draw?")
    thread_id = ask(client, "Wiring?").json()["thread_id"]
    calls_before = len(proxy.calls)

    body = ask(client, "Power draw?", thread_id=thread_id).json()

    assert body["cache_hit"] is False
    assert len(proxy.calls) > calls_before


def test_unknown_request_has_no_receipt(client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/requests/{missing}/receipt").status_code == 404


def test_query_embedding_is_on_the_receipt(client: TestClient, retriever: FakeRetriever) -> None:
    retriever.embed = Usage(
        alias="embed",
        model="text-embedding-3-small",
        provider="openai",
        input_tokens=9,
        output_tokens=0,
        cached_tokens=0,
        usd=Decimal("0.0000002"),
        latency_ms=4,
    )
    request_id = ask(client, "Power draw?").json()["request_id"]

    calls = client.get(f"/requests/{request_id}/receipt").json()["calls"]

    assert [call["stage"] for call in calls] == ["router", "embed", "answer"]


def test_retrieved_passages_are_recorded_with_the_cited_one_marked(
    client: TestClient, engine: Engine
) -> None:
    request_id = ask(client, "Power draw?").json()["request_id"]

    with engine.connect() as conn:
        rows = conn.execute(
            select(RequestChunk.chunk_id, RequestChunk.rank, RequestChunk.used_in_answer)
            .where(RequestChunk.request_id == uuid.UUID(request_id))
            .order_by(RequestChunk.rank)
        ).all()

    assert [(str(chunk_id), rank, used) for chunk_id, rank, used in rows] == [
        (CHUNK_1, 1, True),
        (CHUNK_2, 2, False),
    ]
