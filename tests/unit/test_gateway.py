"""Behaviour: the gateway reads model, provider, tokens and cost from proxy responses."""

import json
from decimal import Decimal

import httpx
import pytest

from bas_assistant.agent.state import AnswerOut
from bas_assistant.llm.gateway import GatewayError, complete

pytestmark = pytest.mark.unit

_MESSAGES = [{"role": "user", "content": "hi"}]


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(base_url="http://litellm.test", transport=handler)


def test_completion_reports_the_fallback_deployment_that_answered() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {
                    "prompt_tokens": 1200,
                    "completion_tokens": 80,
                    "prompt_tokens_details": {"cached_tokens": 1024},
                },
            },
            headers={
                "x-litellm-model-id": "gemini/gemini-2.5-flash",
                "x-litellm-response-cost": "0.000123",
            },
        )

    completion = complete(_client(httpx.MockTransport(handler)), "fast", _MESSAGES, AnswerOut, 50)

    usage = completion.usage
    assert (usage.provider, usage.model, usage.alias) == ("gemini", "gemini-2.5-flash", "fast")
    assert (usage.input_tokens, usage.output_tokens, usage.cached_tokens) == (1200, 80, 1024)
    assert usage.usd == Decimal("0.000123")


def test_request_asks_for_the_output_schema_by_alias() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1}}
        )

    complete(_client(httpx.MockTransport(handler)), "strong", _MESSAGES, AnswerOut, 50)

    body = json.loads(seen[0].content)
    assert body["model"] == "strong"
    assert body["response_format"]["json_schema"]["name"] == "AnswerOut"


def test_proxy_error_after_its_fallbacks_raises_gateway_error() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(503, json={"error": {}}))

    with pytest.raises(GatewayError):
        complete(_client(transport), "fast", _MESSAGES, AnswerOut, 50)


def test_unreachable_proxy_raises_gateway_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(GatewayError):
        complete(_client(httpx.MockTransport(handler)), "fast", _MESSAGES, AnswerOut, 50)
