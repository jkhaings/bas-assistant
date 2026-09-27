"""Calls to the LiteLLM proxy by alias (fast / strong / embed). No vendor SDK in the app.

The proxy owns model choice, provider fallbacks, virtual-key budgets and the price
sheet; each response carries the deployment that served it and its USD cost.
"""

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

Alias = Literal["fast", "strong", "embed"]


class GatewayError(Exception):
    """The proxy could not serve the alias, after its own retries and fallbacks."""


class KeyBudgetError(GatewayError):
    """The proxy refused the app's virtual key: its budget for the period is spent."""


@dataclass(frozen=True)
class Usage:
    alias: Alias
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    usd: Decimal
    latency_ms: int


@dataclass(frozen=True)
class Completion:
    content: str
    usage: Usage


class _ErrorDetail(BaseModel):
    type: str | None = None


class _ErrorBody(BaseModel):
    error: _ErrorDetail


def _is_budget_refusal(response: httpx.Response) -> bool:
    # LiteLLM answers a spent virtual key with 429 and error type "budget_exceeded"
    # (checked live against the pinned proxy with a max_budget 0 key).
    if response.status_code != httpx.codes.TOO_MANY_REQUESTS:
        return False
    try:
        return _ErrorBody.model_validate_json(response.text).error.type == "budget_exceeded"
    except ValidationError:
        return False


class _TokenDetails(BaseModel):
    cached_tokens: int | None = None


class _TokenCounts(BaseModel):
    prompt_tokens: int
    completion_tokens: int = 0
    prompt_tokens_details: _TokenDetails | None = None


def _post(client: httpx.Client, path: str, body: dict[str, object]) -> tuple[httpx.Response, int]:
    started = time.perf_counter()
    try:
        response = client.post(path, json=body)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if _is_budget_refusal(exc.response):
            raise KeyBudgetError(f"{body['model']}: virtual key budget spent") from exc
        raise GatewayError(f"{body['model']}: {exc}") from exc
    except httpx.HTTPError as exc:
        raise GatewayError(f"{body['model']}: {exc}") from exc
    return response, round((time.perf_counter() - started) * 1000)


def parse_usage(alias: Alias, response: httpx.Response, latency_ms: int) -> Usage:
    # The deployment id is "<provider>/<model>" in config/litellm.yaml, so a
    # fallback shows up here as the model that actually answered.
    deployment = response.headers.get("x-litellm-model-id", f"unknown/{alias}")
    provider, _, model = deployment.partition("/")
    counts = _TokenCounts.model_validate(response.json()["usage"])
    details = counts.prompt_tokens_details or _TokenDetails()
    return Usage(
        alias=alias,
        model=model,
        provider=provider,
        input_tokens=counts.prompt_tokens,
        output_tokens=counts.completion_tokens,
        cached_tokens=details.cached_tokens or 0,
        usd=Decimal(response.headers.get("x-litellm-response-cost", "0")),
        latency_ms=latency_ms,
    )


def complete(
    client: httpx.Client,
    alias: Alias,
    messages: list[dict[str, str]],
    output: type[BaseModel],
    max_tokens: int,
) -> Completion:
    """Chat completion constrained to the JSON schema of `output`; the caller validates it."""
    body: dict[str, object] = {
        "model": alias,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": output.__name__,
                "schema": output.model_json_schema(),
                "strict": True,
            },
        },
    }
    response, latency_ms = _post(client, "/v1/chat/completions", body)
    content = response.json()["choices"][0]["message"]["content"] or ""
    return Completion(content=content, usage=parse_usage(alias, response, latency_ms))
