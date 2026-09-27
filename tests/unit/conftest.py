"""Unit fixtures: SQLite for the tables, fakeredis, in-memory checkpointer, fake proxy."""

from collections.abc import Iterator
from decimal import Decimal

import fakeredis
import httpx
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr
from redis import Redis
from sqlalchemy import Engine, create_engine, insert
from sqlalchemy.pool import StaticPool

from bas_assistant.agent.graph import CHECKPOINT_SERDE, build_graph
from bas_assistant.agent.nodes import AgentContext
from bas_assistant.db import metadata, users
from bas_assistant.runtime import AppRuntime
from tests.fakes import ADMIN_TOKEN, FakeProxy, FakeRetriever, make_client


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            insert(users),
            [
                {"email": "support@demo.local", "role": "support"},
                {"email": "engineer@demo.local", "role": "engineer"},
                {"email": "admin@demo.local", "role": "admin"},
                {"email": "svc@demo.local", "role": "support", "api_key_hash": "x"},
            ],
        )
    yield engine
    engine.dispose()


@pytest.fixture
def redis() -> Redis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def proxy() -> FakeProxy:
    return FakeProxy()


@pytest.fixture
def retriever() -> FakeRetriever:
    return FakeRetriever()


@pytest.fixture
def runtime(engine: Engine, redis: Redis, proxy: FakeProxy, retriever: FakeRetriever) -> AppRuntime:
    llm = httpx.Client(base_url="http://litellm.test", transport=httpx.MockTransport(proxy))
    return AppRuntime(
        agent=AgentContext(llm=llm, engine=engine, retrieve=retriever),
        graph=build_graph(InMemorySaver(serde=CHECKPOINT_SERDE)),
        redis=redis,
        admin_token=SecretStr(ADMIN_TOKEN),
        daily_usd_cap=Decimal(3),
        user_daily_questions=50,
        corpus_version="test",
    )


@pytest.fixture
def client(runtime: AppRuntime) -> TestClient:
    return make_client(runtime)
