"""The running stack end to end: app, proxy, providers, corpus (`make up && make ingest`,
then `make eval`; never in CI). Questions come from data/top20_questions.md.
"""

import json
import logging
import os
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from redis import Redis

from bas_assistant.agent.prompts import PROMPT_VERSION
from bas_assistant.cost.cache import cache_key
from bas_assistant.settings import Settings

pytestmark = pytest.mark.eval

logger = logging.getLogger(__name__)

APP_URL = "http://localhost:8000"
# The spot check in data/top20_questions.md; its top passage holds the answer.
CACHED_QUESTION = "What is the power draw of the O3 Sense?"
ENGINEER_ONLY_QUESTION = "What makes the DAC-633PoE suitable for fan coil applications?"  # row 19


@pytest.fixture
def app() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=APP_URL, timeout=180) as client:
        yield client


def _forget(question: str, role: str) -> None:
    """Drop a cached answer so the first ask of a run really reaches the models."""
    settings = Settings()
    with Redis.from_url(os.environ["REDIS_URL"]) as redis:
        redis.delete(cache_key(question, role, settings.corpus_version, PROMPT_VERSION))


def _ask(app: httpx.Client, question: str, role: str) -> dict[str, Any]:
    """The decoded /ask response body."""
    body: dict[str, Any] = app.post(
        "/ask", json={"question": question}, headers={"X-Demo-Role": role}
    ).json()
    logger.info("ask %s -> %s", role, json.dumps(body))
    return body


def _receipt(app: httpx.Client, request_id: str) -> dict[str, Any]:
    """The decoded receipt body."""
    receipt: dict[str, Any] = app.get(f"/requests/{request_id}/receipt").json()
    logger.info("receipt -> %s", json.dumps(receipt))
    return receipt


@pytest.mark.parametrize(
    ("group", "deployment"),
    [("fast-fallback", "gemini/gemini-3.8-flash"), ("strong-fallback", "openai/gpt-4o")],
)
def test_each_fallback_deployment_still_answers(group: str, deployment: str) -> None:
    # Vendors retire models; a dead fallback only shows up on the day the primary fails.
    with httpx.Client(
        base_url=os.environ["LITELLM_BASE_URL"],
        headers={"Authorization": f"Bearer {os.environ['LITELLM_API_KEY']}"},
        timeout=60,
    ) as proxy:
        response = proxy.post(
            "/v1/chat/completions",
            json={
                "model": group,
                "messages": [{"role": "user", "content": "Reply with the word ok."}],
                "max_tokens": 200,
            },
        )
    logger.info(
        "%s -> %s %s", group, response.status_code, response.headers.get("x-litellm-model-id")
    )
    assert response.status_code == 200
    assert response.headers["x-litellm-model-id"] == deployment


def test_same_question_twice_costs_nothing_the_second_time(app: httpx.Client) -> None:
    _forget(CACHED_QUESTION, "support")
    first = _ask(app, CACHED_QUESTION, "support")
    second = _ask(app, CACHED_QUESTION, "support")

    first_receipt = _receipt(app, first["request_id"])
    second_receipt = _receipt(app, second["request_id"])

    assert first["decision"] == "answered"
    assert first["citations"]
    assert first_receipt["usd"] > 0
    assert (second_receipt["cache_hit"], second_receipt["usd"]) == (True, 0.0)


def test_engineer_only_document_is_invisible_to_support(app: httpx.Client) -> None:
    for role in ("support", "engineer"):
        _forget(ENGINEER_ONLY_QUESTION, role)

    support = _ask(app, ENGINEER_ONLY_QUESTION, "support")
    engineer = _ask(app, ENGINEER_ONLY_QUESTION, "engineer")

    assert (support["decision"], support["citations"]) == ("abstained", [])
    assert engineer["decision"] == "answered"
    assert any("DAC-633PoE" in c["document_title"] for c in engineer["citations"])
