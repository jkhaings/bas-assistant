"""Live models through the local LiteLLM proxy (`make eval`; never in CI).

Retrieval is the synthetic fixture until session A's corpus merges; everything else
is real: proxy, providers, Postgres checkpointer, Redis. Each test costs under a cent.
"""

import json
import logging
import os
from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres import PostgresSaver
from pydantic import SecretStr
from redis import Redis

from bas_assistant.agent.graph import CHECKPOINT_SERDE, build_graph
from bas_assistant.agent.nodes import AgentContext
from bas_assistant.db import create_db_engine
from bas_assistant.runtime import AppRuntime, checkpoint_pool
from tests.fakes import FakeRetriever, make_client

pytestmark = pytest.mark.eval

logger = logging.getLogger(__name__)

_ADMIN_TOKEN = "eval-admin-token"


def _proxy() -> httpx.Client:
    return httpx.Client(
        base_url=os.environ["LITELLM_BASE_URL"],
        headers={"Authorization": f"Bearer {os.environ['LITELLM_API_KEY']}"},
        timeout=60,
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_db_engine(os.environ["DATABASE_URL"])
    with checkpoint_pool(os.environ["DATABASE_URL"]) as pool, _proxy() as llm:
        saver = PostgresSaver(pool, serde=CHECKPOINT_SERDE)
        saver.setup()
        runtime = AppRuntime(
            agent=AgentContext(llm=llm, engine=engine, retrieve=FakeRetriever()),
            graph=build_graph(saver),
            redis=Redis.from_url(os.environ["REDIS_URL"], decode_responses=True),
            admin_token=SecretStr(_ADMIN_TOKEN),
            daily_usd_cap=Decimal(1),
            user_daily_questions=1000,
            corpus_version=str(uuid4()),
        )
        yield make_client(runtime)
    engine.dispose()


def _ask(client: TestClient, question: str, role: str = "support") -> dict[str, Any]:
    """The decoded /ask response body."""
    body: dict[str, Any] = client.post(
        "/ask", json={"question": question}, headers={"X-Demo-Role": role}
    ).json()
    logger.info("ask %s -> %s", role, json.dumps(body))
    return body


def _receipt(client: TestClient, request_id: str) -> dict[str, Any]:
    """The decoded receipt body."""
    receipt: dict[str, Any] = client.get(f"/requests/{request_id}/receipt").json()
    logger.info("receipt -> %s", json.dumps(receipt))
    return receipt


@pytest.mark.parametrize(
    ("group", "deployment"),
    [("fast-fallback", "gemini/gemini-3.8-flash"), ("strong-fallback", "openai/gpt-4o")],
)
def test_each_fallback_deployment_still_answers(group: str, deployment: str) -> None:
    # Vendors retire models; a dead fallback only shows up on the day the primary fails.
    with _proxy() as proxy:
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
    assert float(response.headers["x-litellm-response-cost"]) > 0


def test_same_question_twice_costs_nothing_the_second_time(client: TestClient) -> None:
    first = _ask(client, "How much power does the sample controller draw?")
    second = _ask(client, "How much power does the sample controller draw?")

    first_receipt = _receipt(client, first["request_id"])
    second_receipt = _receipt(client, second["request_id"])

    assert first["decision"] == "answered"
    assert first_receipt["usd"] > 0
    assert (second_receipt["cache_hit"], second_receipt["usd"]) == (True, 0.0)


def test_complex_question_routes_to_the_strong_model(client: TestClient) -> None:
    body = _ask(
        client,
        "Compare the sample controller's power draw with its replacement-parts process and "
        "explain step by step what a technician should check before ordering parts.",
    )

    receipt = _receipt(client, body["request_id"])

    assert body["route"] == "strong"
    assert receipt["route"] == "strong"
    assert str(receipt["model"]).startswith("claude-sonnet")


def test_ticket_request_pauses_and_needs_the_admin_token_to_file(client: TestClient) -> None:
    body = _ask(
        client,
        "Please open a support ticket: the sample controller at site 12 arrived with a "
        "cracked housing and we need a replacement.",
        role="engineer",
    )
    assert body["decision"] == "paused"
    approve = {"thread_id": body["thread_id"], "approve": True}

    without_token = client.post("/approve", json=approve)
    with_token = client.post("/approve", json=approve, headers={"X-Admin-Token": _ADMIN_TOKEN})

    logger.info("approve without token -> %s %s", without_token.status_code, without_token.text)
    logger.info("approve with token -> %s %s", with_token.status_code, with_token.text)
    assert without_token.status_code == 401
    assert with_token.json()["status"] == "filed"
