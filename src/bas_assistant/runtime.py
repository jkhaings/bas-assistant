"""Long-lived clients the API needs, opened once at startup."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal

import httpx
from fastapi import Request
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool
from pydantic import SecretStr
from redis import Redis

from bas_assistant.agent.graph import CHECKPOINT_SERDE, Graph, build_graph
from bas_assistant.agent.nodes import AgentContext
from bas_assistant.agent.state import Retriever
from bas_assistant.db import create_db_engine
from bas_assistant.settings import Settings


@dataclass(frozen=True)
class AppRuntime:
    agent: AgentContext
    graph: Graph
    redis: Redis
    admin_token: SecretStr
    daily_usd_cap: Decimal
    user_daily_questions: int
    corpus_version: str


def checkpoint_pool(database_url: str) -> ConnectionPool[Connection[DictRow]]:
    """Connection settings langgraph-checkpoint-postgres requires for a shared pool."""
    return ConnectionPool(
        database_url,
        connection_class=Connection[DictRow],
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )


@contextmanager
def open_runtime(settings: Settings, retrieve: Retriever) -> Iterator[AppRuntime]:
    database_url = settings.database_url.get_secret_value()
    engine = create_db_engine(database_url)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    llm = httpx.Client(
        base_url=settings.litellm_base_url,
        headers={"Authorization": f"Bearer {settings.litellm_api_key.get_secret_value()}"},
        # Longer than the proxy's worst case: strong, strong-fallback, fast and fast's own
        # fallback, 30 s each (config/litellm.yaml).
        timeout=130,
    )
    with checkpoint_pool(database_url) as pool, llm, redis:
        checkpointer = PostgresSaver(pool, serde=CHECKPOINT_SERDE)
        checkpointer.setup()
        yield AppRuntime(
            agent=AgentContext(llm=llm, engine=engine, retrieve=retrieve),
            graph=build_graph(checkpointer),
            redis=redis,
            admin_token=settings.admin_token,
            daily_usd_cap=settings.daily_usd_cap,
            user_daily_questions=settings.user_daily_questions,
            corpus_version=settings.corpus_version,
        )
    engine.dispose()


def get_runtime(request: Request) -> AppRuntime:
    runtime: AppRuntime = request.app.state.runtime
    return runtime
