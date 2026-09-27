"""Behaviour: `make litellm-keys` creates each virtual key once, then updates its budget."""

import json

import httpx
import pytest

from bas_assistant.llm.provision import register

pytestmark = pytest.mark.unit


def _proxy(existing_keys: set[str]) -> tuple[httpx.Client, list[tuple[str, dict[str, object]]]]:
    sent: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append((request.url.path, body))
        if request.url.path == "/key/generate" and body["key"] in existing_keys:
            return httpx.Response(400, json={"error": "key already exists"})
        return httpx.Response(200, json={})

    return httpx.Client(
        base_url="http://litellm.test", transport=httpx.MockTransport(handler)
    ), sent


def test_new_key_is_created_with_its_monthly_budget() -> None:
    client, sent = _proxy(existing_keys=set())

    register(client, "dev", "virtual-key-1", 5.0)

    assert sent == [
        (
            "/key/generate",
            {
                "key": "virtual-key-1",
                "key_alias": "dev",
                "max_budget": 5.0,
                "budget_duration": "30d",
            },
        )
    ]


def test_existing_key_gets_its_budget_updated() -> None:
    client, sent = _proxy(existing_keys={"virtual-key-1"})

    register(client, "dev", "virtual-key-1", 7.0)

    assert [path for path, _ in sent] == ["/key/generate", "/key/update"]
    assert sent[1][1]["max_budget"] == 7.0


def test_failed_update_is_raised() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(500, json={}))
    client = httpx.Client(base_url="http://litellm.test", transport=transport)

    with pytest.raises(httpx.HTTPStatusError):
        register(client, "dev", "virtual-key-1", 5.0)
