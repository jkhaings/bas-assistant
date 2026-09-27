"""Behaviour against real Postgres and Redis from docker compose (`make test-int`).

The model is still the fake proxy; what is real here is the schema from the Alembic
migrations, the PostgresSaver checkpointer, request_chunks against real chunk rows, and the
daily-cap query.
"""

import logging
import os
import uuid
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
from sqlalchemy import Engine, create_engine, insert, select
from sqlalchemy.orm import Session

from bas_assistant.agent.graph import CHECKPOINT_SERDE, build_graph
from bas_assistant.agent.nodes import AgentContext
from bas_assistant.cost.budget import spent_today
from bas_assistant.db.activity import Request, RequestChunk, Ticket, Usage
from bas_assistant.db.corpus import Chunk
from bas_assistant.runtime import AppRuntime, checkpoint_pool
from bas_assistant.settings import Settings
from tests.fakes import make_chunk, make_document, make_parent
from tests.graph_fakes import CHUNK_1, CHUNK_2, FakeProxy, FakeRetriever, answer_json, make_client

pytestmark = pytest.mark.integration

_ADMIN_TOKEN = "integration-admin-token"


def _database_url() -> str:
    return Settings().database_url


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = create_engine(_database_url())
    _seed_fixture_chunks(engine)
    yield engine
    engine.dispose()


def _seed_fixture_chunks(engine: Engine) -> None:
    """Real corpus rows behind the fake retriever's passage ids, for request_chunks' FK."""
    document = make_document(title="Sample Controller Catalog Sheet")
    parent = make_parent(document)
    chunks = [make_chunk(parent, text=f"fixture chunk {n}") for n in (1, 2)]
    for chunk, chunk_id in zip(chunks, (CHUNK_1, CHUNK_2), strict=True):
        chunk.id = uuid.UUID(chunk_id)
    with Session(engine) as session:
        if session.get(Chunk, chunks[0].id) is None:
            session.add_all([document, parent, *chunks])
            session.commit()


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
        ip_rate_limit=1000,
    )


def test_paused_ticket_survives_a_restart_and_is_filed_on_approval(
    engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    proxy = FakeProxy(answers=[answer_json(answer="Drafted.", ticket_title="Replace unit")])
    with checkpoint_pool(_database_url()) as pool:
        asked = make_client(_runtime(engine, pool, proxy)).post(
            "/ask",
            json={"question": "Open a ticket to replace the unit"},
            headers={"X-Demo-Role": "engineer"},
        )
    assert asked.json()["decision"] == "paused"

    # A new pool, checkpointer and graph: nothing survives in memory from the ask.
    with checkpoint_pool(_database_url()) as pool, caplog.at_level(logging.WARNING):
        client = make_client(_runtime(engine, pool, FakeProxy()))
        approved = client.post(
            "/approve",
            json={"thread_id": asked.json()["thread_id"], "approve": True},
            headers={"X-Admin-Token": _ADMIN_TOKEN, "X-Demo-Role": "admin"},
        )
        history = client.get(
            f"/threads/{asked.json()['thread_id']}/history", headers={"X-Demo-Role": "engineer"}
        ).json()

    assert approved.json()["status"] == "filed"
    assert history == [{"question": "Open a ticket to replace the unit", "answer": "Drafted."}]
    with engine.connect() as conn:
        status: str = conn.execute(
            select(Ticket.status).where(Ticket.id == asked.json()["ticket_id"])
        ).scalar_one()
        decision: str | None = conn.execute(
            select(Request.decision).where(Request.id == asked.json()["request_id"])
        ).scalar_one()
        recorded = conn.execute(
            select(RequestChunk.chunk_id, RequestChunk.used_in_answer)
            .where(RequestChunk.request_id == asked.json()["request_id"])
            .order_by(RequestChunk.rank)
        ).all()
    assert (status, decision) == ("filed", "answered")
    assert [(str(chunk_id), used) for chunk_id, used in recorded] == [
        (CHUNK_1, True),
        (CHUNK_2, False),
    ]
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
            insert(Usage),
            [
                {**row, "usd": Decimal("0.25"), "created_at": now},
                {**row, "usd": Decimal(7), "created_at": now - timedelta(days=1)},
            ],
        )

    assert spent_today(engine, now) - before == Decimal("0.25")
