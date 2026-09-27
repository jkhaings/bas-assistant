"""Behaviour: the embedder calls the configured endpoint and reports tokens and cost."""

from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from bas_assistant.retrieval.embeddings import OpenAIEmbedder
from bas_assistant.settings import Settings

pytestmark = pytest.mark.unit


def _settings() -> Settings:
    return Settings(
        openai_api_key=SecretStr("sk-test"),
        anthropic_api_key=SecretStr("test"),
        gemini_api_key=SecretStr("test"),
        admin_token=SecretStr("test"),
        grafana_admin_password=SecretStr("test"),
        postgres_password=SecretStr("test"),
    )


def test_embed_returns_vectors_tokens_and_cost() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        assert request.headers["authorization"] == "Bearer sk-test"
        return httpx.Response(
            200,
            json={
                "data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}],
                "usage": {"total_tokens": 7},
            },
        )

    embedder = OpenAIEmbedder(_settings(), transport=httpx.MockTransport(handler))
    result = embedder.embed(["hello", "world"])

    assert result.vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert result.input_tokens == 7
    assert result.usd == (Decimal(7) / Decimal(1_000_000)) * Decimal("0.02")


def test_embed_raises_on_an_http_error() -> None:
    embedder = OpenAIEmbedder(
        _settings(), transport=httpx.MockTransport(lambda _request: httpx.Response(500))
    )

    with pytest.raises(httpx.HTTPStatusError):
        embedder.embed(["hello"])
