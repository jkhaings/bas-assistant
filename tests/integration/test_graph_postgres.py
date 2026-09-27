"""Behaviour against real Postgres and Redis from docker compose (`make test-int`).

The model is still the fake proxy; what is real here is the schema from the Alembic
migration, the PostgresSaver checkpointer and the daily-cap query.
"""

import logging
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool
from pydantic import SecretStr
from redis import Redis
from sqlalchemy import Engine, insert, select

from bas_assistant.agent.graph import CHECKPOINT_SERDE, build_graph
from bas_assistant.agent.nodes import AgentContext
from bas_assistant.cost.budget import spent_today
from bas_assistant.db import create_db_engine, requests, tickets, usage
from bas_assistant.runtime import AppRuntime, checkpoint_pool
from tests.fakes import FakeProxy, FakeRetriever, answer_json, make_client

pytestmark = pytest.mark.integration

_ADMIN_TOKEN = "integration-admin-token"


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = create_db_engine(os.environ["DATABASE_URL"])
    yield engine
    engine.dispose()


def _runtime(
    engine: Engine, pool: ConnectionPool[Connection[DictRow]], proxy: FakeProxy
) -> AppRuntime:
    saver = PostgresSaver(pool, serde=CHECKPOINT_SERDE)
    saver.setup()
    llm = httpx.Client(base_url="http://litellm.test", transport=httpx.MockTransport(proxy))
    return AppRuntime(
        agent=AgentContext(llm=llm, engine=engine, retrieve=FakeRetriever()),
        graph=build_graph(saver),
        redis=Redis.from_url(os.environ["REDIS_URL"], decode_responses=True),
        admin_token=SecretStr(_ADMIN_TOKEN),
        daily_usd_cap=Decimal(1000),
        user_daily_questions=1000,
        corpus_version=str(uuid4()),
    )


def test_paused_ticket_survives_a_restart_and_is_filed_on_approval(
    engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    proxy = FakeProxy(answers=[answer_json(answer="Drafted.", ticket_title="Replace unit")])
    with checkpoint_pool(os.environ["DATABASE_URL"]) as pool:
        asked = make_client(_runtime(engine, pool, proxy)).post(
            "/ask",
            json={"question": "Open a ticket to replace the unit"},
            headers={"X-Demo-Role": "engineer"},
        )
    assert asked.json()["decision"] == "paused"

    # A new pool, checkpointer and graph: nothing survives in memory from the ask.
    with checkpoint_pool(os.environ["DATABASE_URL"]) as pool, caplog.at_level(logging.WARNING):
        client = make_client(_runtime(engine, pool, FakeProxy()))
        approved = client.post(
            "/approve",
            json={"thread_id": asked.json()["thread_id"], "approve": True},
            headers={"X-Admin-Token": _ADMIN_TOKEN},
        )
        history = client.get(
            f"/threads/{asked.json()['thread_id']}/history", headers={"X-Demo-Role": "engineer"}
        ).json()

    assert approved.json()["status"] == "filed"
    assert history == [{"question": "Open a ticket to replace the unit", "answer": "Drafted."}]
    with engine.connect() as conn:
        status: str = conn.execute(
            select(tickets.c.status).where(tickets.c.id == asked.json()["ticket_id"])
        ).scalar_one()
        decision: str = conn.execute(
            select(requests.c.decision).where(requests.c.id == asked.json()["request_id"])
        ).scalar_one()
    assert (status, decision) == ("filed", "answered")
    assert not [r.message for r in caplog.records if "serializ" in r.message.lower()]


def test_daily_spend_counts_only_rows_since_utc_midnight(engine: Engine) -> None:
    now = datetime.now(UTC)
    before = spent_today(engine, now)
    row = {
        "stage": "answer",
        "alias": "fast",
        "model": "m",
        "provider": "p",
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "latency_ms": 0,
        "cache_hit": False,
    }
    with engine.begin() as conn:
        conn.execute(
            insert(usage),
            [
                {**row, "usd": Decimal("0.25"), "created_at": now},
                {**row, "usd": Decimal(7), "created_at": now - timedelta(days=1)},
            ],
        )

    assert spent_today(engine, now) - before == Decimal("0.25")
