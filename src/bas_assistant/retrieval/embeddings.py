"""Embedding provider: an OpenAI-compatible /v1/embeddings client.

Session B repoints embed_base_url/embed_model at the LiteLLM proxy's `embed`
alias by settings change only — nothing here imports a vendor SDK.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Protocol

import httpx
from pydantic import BaseModel

from bas_assistant.settings import Settings


class EmbedBatch(BaseModel):
    """The result of embedding one batch of texts."""

    vectors: list[list[float]]
    input_tokens: int
    usd: Decimal
    latency_ms: int


class EmbeddingProvider(Protocol):
    """Anything that can turn text into vectors and report what it cost."""

    model: str

    def embed(self, texts: list[str]) -> EmbedBatch: ...


class OpenAIEmbedder:
    """Calls an OpenAI-compatible /v1/embeddings endpoint."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.model = settings.embed_model
        self._usd_per_mtok = settings.embed_usd_per_mtok
        self._client = httpx.Client(
            base_url=settings.embed_base_url,
            headers={"Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}"},
            timeout=30.0,
            transport=transport,  # tests substitute an httpx.MockTransport
        )

    def embed(self, texts: list[str]) -> EmbedBatch:
        start = time.monotonic()
        response = self._client.post("/embeddings", json={"model": self.model, "input": texts})
        response.raise_for_status()
        body = response.json()
        latency_ms = int((time.monotonic() - start) * 1000)
        vectors = [item["embedding"] for item in body["data"]]
        tokens = int(body["usage"]["total_tokens"])
        usd = (Decimal(tokens) / Decimal(1_000_000)) * self._usd_per_mtok
        return EmbedBatch(vectors=vectors, input_tokens=tokens, usd=usd, latency_ms=latency_ms)
