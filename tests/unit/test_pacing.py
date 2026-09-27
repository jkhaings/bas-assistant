"""Behaviour: a paced client sends no more than the app's per-IP limit in any window, and does
not slow down below it."""

import time

import httpx
import pytest

from bas_assistant.evals.pacing import pacing_hook

pytestmark = pytest.mark.unit


def _paced_client(limit: int, window_s: float) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200)),
        event_hooks={"request": [pacing_hook(limit, window_s)]},
    )


def _seconds_to_send(client: httpx.Client, requests: int) -> float:
    start = time.monotonic()
    for _ in range(requests):
        client.post("http://app.test/ask")
    return time.monotonic() - start


def test_requests_up_to_the_limit_go_out_without_waiting() -> None:
    with _paced_client(limit=3, window_s=5) as client:
        # Waiting at all would take most of the 5 s window.
        assert _seconds_to_send(client, 3) < 2.5


def test_request_over_the_limit_waits_for_the_window() -> None:
    with _paced_client(limit=2, window_s=0.3) as client:
        # Short of 0.3 only by timer slack; an unpaced client takes milliseconds.
        assert _seconds_to_send(client, 3) >= 0.25
