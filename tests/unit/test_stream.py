"""Behaviour: /ask/stream sends node events as the graph runs, then the validated answer."""

import json
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bas_assistant.runtime import AppRuntime
from tests.graph_fakes import FakeProxy, ask, make_client

pytestmark = pytest.mark.unit


def _events(client: TestClient, question: str) -> list[tuple[str, Any]]:
    """(event name, decoded JSON data) pairs."""
    response = client.post(
        "/ask/stream", json={"question": question}, headers={"X-Demo-Role": "support"}
    )
    assert response.headers["content-type"].startswith("text/event-stream")
    events: list[tuple[str, Any]] = []
    for block in response.text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def test_stream_reports_each_node_then_the_answer(client: TestClient) -> None:
    events = _events(client, "Power draw?")

    nodes = [data["node"] for name, data in events if name == "node"]
    assert nodes == ["screen", "route", "retrieve", "answer", "validate", "finish"]
    name, answer = events[-1]
    assert name == "answer"
    assert answer["decision"] == "answered"


def test_stream_of_a_cached_question_is_just_the_answer(client: TestClient) -> None:
    _events(client, "Power draw?")

    events = _events(client, "Power draw?")

    assert [name for name, _ in events] == ["answer"]


def test_model_outage_mid_stream_sends_an_error_and_refunds_the_question(
    runtime: AppRuntime, proxy: FakeProxy
) -> None:
    client = make_client(replace(runtime, user_daily_questions=1))
    proxy.down = {"fast", "strong"}

    events = _events(client, "Power draw?")
    proxy.down = set()

    # screen is code only, so its node event arrives before the router call fails.
    assert events[0] == ("node", {"node": "screen"})
    assert events[-1][0] == "error"
    assert events[-1][1]["reason"] == "model_unavailable"
    assert ask(client, "Power draw?").status_code == 200
