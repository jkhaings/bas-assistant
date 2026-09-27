"""Behaviour: /metrics reports what the API did (the registry is process-wide, so deltas)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from sqlalchemy import Engine, select

from bas_assistant.db.activity import Request
from tests.graph_fakes import INPUT_TOKENS, FakeProxy, FakeRetriever, answer_json, ask

pytestmark = pytest.mark.unit


def _value(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_an_answered_question_is_counted_with_its_tokens_and_cost(client: TestClient) -> None:
    requests = _value("bas_requests_total", decision="answered", route="fast")
    tokens = _value("bas_tokens_total", model="gpt-4o-mini", stage="answer", kind="input")
    usd = _value("bas_usd_total", model="gpt-4o-mini", stage="answer")
    http = _value("bas_http_requests_total", method="POST", route="/ask", status="200")

    ask(client, "How much power does the sample controller draw?")

    assert _value("bas_requests_total", decision="answered", route="fast") == requests + 1
    assert (
        _value("bas_tokens_total", model="gpt-4o-mini", stage="answer", kind="input")
        == tokens + INPUT_TOKENS
    )
    assert _value("bas_usd_total", model="gpt-4o-mini", stage="answer") == pytest.approx(
        usd + 0.0001
    )
    assert _value("bas_http_requests_total", method="POST", route="/ask", status="200") == http + 1


def test_metrics_endpoint_serves_the_prometheus_text_format(client: TestClient) -> None:
    ask(client, "How much power does the sample controller draw?")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'bas_requests_total{decision="answered",route="fast"}' in response.text
    assert "bas_request_latency_seconds_bucket" in response.text


def test_a_cache_hit_is_counted(client: TestClient) -> None:
    hits = _value("bas_cache_hits_total")

    ask(client, "What is the supply voltage of the sample controller?")
    ask(client, "What is the supply voltage of the sample controller?")

    assert _value("bas_cache_hits_total") == hits + 1


def test_a_fabricated_citation_counts_a_retry_and_a_failure(
    client: TestClient, proxy: FakeProxy
) -> None:
    proxy.answers = [answer_json(citations=("made-up",)), answer_json(citations=("made-up",))]
    retries = _value("bas_validation_retries_total")
    failures = _value("bas_validation_failures_total")

    ask(client, "How much power does the sample controller draw?")

    assert _value("bas_validation_retries_total") == retries + 1
    assert _value("bas_validation_failures_total") == failures + 1


def test_a_proposed_ticket_is_counted(client: TestClient, proxy: FakeProxy) -> None:
    proxy.answers = [answer_json(ticket_title="Replace the cracked housing")]
    proposed = _value("bas_tickets_total", status="proposed")

    ask(client, "The housing is cracked, can we get a replacement?", role="engineer")

    assert _value("bas_tickets_total", status="proposed") == proposed + 1


def test_errors_are_labelled_by_route_template_not_by_id(client: TestClient) -> None:
    route = "/requests/{request_id}/receipt"
    not_found = _value("bas_http_requests_total", method="GET", route=route, status="404")

    client.get(f"/requests/{uuid4()}/receipt")

    assert (
        _value("bas_http_requests_total", method="GET", route=route, status="404") == not_found + 1
    )


def test_health_probes_are_not_counted(client: TestClient) -> None:
    probes = _value("bas_http_requests_total", method="GET", route="/healthz", status="200")

    client.get("/healthz")

    assert _value("bas_http_requests_total", method="GET", route="/healthz", status="200") == probes


def test_a_crash_outside_the_gateway_still_closes_the_request_as_failed(
    client: TestClient, retriever: FakeRetriever, engine: Engine
) -> None:
    retriever.crash = RuntimeError("database went away")
    failed = _value("bas_requests_total", decision="failed", route="none")

    with pytest.raises(RuntimeError):
        ask(client, "How much power does the sample controller draw?")

    assert _value("bas_requests_total", decision="failed", route="none") == failed + 1
    with engine.connect() as conn:
        decisions = list(conn.execute(select(Request.decision)).scalars())
    assert decisions == ["failed"]
