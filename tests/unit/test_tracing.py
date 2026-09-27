"""Behaviour: a question produces a trace with its steps, model calls and costs, and no
raw question text anywhere in it."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import SecretStr

from bas_assistant.observability.tracing import langfuse_provider
from bas_assistant.settings import Settings
from tests.graph_fakes import ADMIN_TOKEN, INPUT_TOKENS, FakeProxy, answer_json, ask

pytestmark = pytest.mark.unit

_EXPORTER = InMemorySpanExporter()


@pytest.fixture(scope="module", autouse=True)
def _provider() -> None:
    # OpenTelemetry allows one global provider per process; no other test module sets one.
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_EXPORTER))
    trace.set_tracer_provider(provider)


@pytest.fixture
def spans() -> Iterator[InMemorySpanExporter]:
    _EXPORTER.clear()
    yield _EXPORTER
    _EXPORTER.clear()


def _named(exporter: InMemorySpanExporter, name: str) -> list[ReadableSpan]:
    return [span for span in exporter.get_finished_spans() if span.name == name]


def test_a_question_traces_each_step_under_one_request(
    client: TestClient, spans: InMemorySpanExporter
) -> None:
    ask(client, "How much power does the sample controller draw?")

    names = [span.name for span in spans.get_finished_spans()]
    for step in ("node route", "node retrieve", "node answer", "node validate", "POST /ask"):
        assert step in names
    trace_ids = {span.context.trace_id for span in spans.get_finished_spans()}
    assert len(trace_ids) == 1


def test_model_calls_are_generations_with_tokens_and_cost(
    client: TestClient, spans: InMemorySpanExporter
) -> None:
    ask(client, "How much power does the sample controller draw?")

    router, answer = _named(spans, "llm fast")
    attributes = answer.attributes or {}
    assert attributes["langfuse.observation.type"] == "generation"
    assert attributes["langfuse.observation.model.name"] == "gpt-4o-mini"
    assert attributes["gen_ai.usage.input_tokens"] == INPUT_TOKENS
    assert attributes["gen_ai.usage.cost"] == pytest.approx(0.0001)
    assert router.parent is not None


def test_the_trace_carries_session_decision_and_route(
    client: TestClient, spans: InMemorySpanExporter
) -> None:
    body = ask(client, "How much power does the sample controller draw?").json()

    (root,) = _named(spans, "POST /ask")
    attributes = root.attributes or {}
    assert attributes["langfuse.session.id"] == body["thread_id"]
    assert attributes["langfuse.trace.metadata.request_id"] == body["request_id"]
    assert attributes["langfuse.trace.metadata.decision"] == "answered"
    assert attributes["langfuse.trace.metadata.route"] == "fast"


def test_validation_outcome_is_on_the_validate_span(
    client: TestClient, proxy: FakeProxy, spans: InMemorySpanExporter
) -> None:
    proxy.answers = [answer_json(citations=("made-up",)), answer_json(citations=("made-up",))]

    ask(client, "How much power does the sample controller draw?")

    first, second = _named(spans, "node validate")
    assert (first.attributes or {})["agent.validation_errors_count"] == 1
    assert (second.attributes or {})["agent.decision"] == "failed"


def test_a_ticket_pausing_at_the_gate_is_an_event(
    client: TestClient, proxy: FakeProxy, spans: InMemorySpanExporter
) -> None:
    proxy.answers = [answer_json(ticket_title="Replace the cracked housing")]

    body = ask(client, "The housing is cracked, can we get one?", role="engineer").json()

    (paused,) = _named(spans, "gate paused")
    assert (paused.attributes or {})["ticket_id"] == body["ticket_id"]
    assert (paused.attributes or {})["langfuse.observation.type"] == "event"


def test_no_span_carries_the_raw_question(client: TestClient, spans: InMemorySpanExporter) -> None:
    ask(client, "Email jane.doe@example.com the power draw of the sample controller")

    values = [
        str(value)
        for span in spans.get_finished_spans()
        for value in (span.attributes or {}).values()
    ]
    assert values
    assert not [value for value in values if "jane.doe@example.com" in value]
    (root,) = _named(spans, "POST /ask")
    assert "<EMAIL_ADDRESS>" in str((root.attributes or {})["langfuse.trace.input"])
    assert "<EMAIL_ADDRESS>" in str((root.attributes or {})["langfuse.observation.input"])


def test_the_root_span_keeps_no_user_agent_or_client_address(
    client: TestClient, spans: InMemorySpanExporter
) -> None:
    client.post(
        "/ask",
        json={"question": "How much power does the sample controller draw?"},
        headers={"User-Agent": "Mozilla/5.0 visitor-browser"},
    )

    (root,) = _named(spans, "POST /ask")
    values = [str(value) for value in (root.attributes or {}).values()]
    assert not [value for value in values if "visitor-browser" in value or "testclient" in value]


def test_a_streamed_question_traces_its_steps_under_one_request(
    client: TestClient, spans: InMemorySpanExporter
) -> None:
    client.post("/ask/stream", json={"question": "How much power does the sample controller draw?"})

    names = [span.name for span in spans.get_finished_spans()]
    assert {"POST /ask/stream", "node route", "node answer", "node validate"} <= set(names)
    assert len({span.context.trace_id for span in spans.get_finished_spans()}) == 1


def test_an_approval_records_the_gate_resuming(
    client: TestClient, proxy: FakeProxy, spans: InMemorySpanExporter
) -> None:
    proxy.answers = [answer_json(ticket_title="Replace the cracked housing")]
    body = ask(client, "The housing is cracked, can we get one?", role="engineer").json()
    spans.clear()

    client.post(
        "/approve",
        json={"thread_id": body["thread_id"], "approve": True},
        headers={"X-Admin-Token": ADMIN_TOKEN, "X-Demo-Role": "admin"},
    )

    (resumed,) = _named(spans, "gate resumed")
    assert (resumed.attributes or {})["approve"] is True
    (root,) = _named(spans, "POST /approve")
    assert (root.attributes or {})["langfuse.session.id"] == body["thread_id"]
    assert _named(spans, "node act")


def _settings(public_key: str | None, secret_key: str | None) -> Settings:
    return Settings(
        openai_api_key=SecretStr("test"),
        anthropic_api_key=SecretStr("test"),
        gemini_api_key=SecretStr("test"),
        admin_token=SecretStr("test"),
        grafana_admin_password=SecretStr("test"),
        postgres_password=SecretStr("test"),
        litellm_api_key=SecretStr("test"),
        langfuse_public_key=SecretStr(public_key) if public_key is not None else None,
        langfuse_secret_key=SecretStr(secret_key) if secret_key is not None else None,
    )


def test_without_langfuse_keys_nothing_is_exported() -> None:
    assert langfuse_provider(_settings(None, None)) is None
    # An env file with the variable present but empty counts as no key.
    assert langfuse_provider(_settings("", "")) is None


def test_with_langfuse_keys_spans_go_to_its_otlp_endpoint() -> None:
    provider = langfuse_provider(_settings("pk-lf-test", "sk-lf-test"))

    assert provider is not None
    provider.shutdown()
