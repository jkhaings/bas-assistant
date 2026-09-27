"""Long-lived clients the API needs, opened once at startup."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from functools import partial

import httpx
from fastapi import Request
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool
from pydantic import SecretStr
from redis import Redis
from sqlalchemy import make_url

from bas_assistant.agent.graph import CHECKPOINT_SERDE, Graph, build_graph
from bas_assistant.agent.nodes import AgentContext
from bas_assistant.agent.state import Retriever
from bas_assistant.db.corpus import current_corpus_version
from bas_assistant.db.engine import get_engine
from bas_assistant.settings import Settings


@dataclass(frozen=True)
class AppRuntime:
    agent: AgentContext
    graph: Graph
    redis: Redis
    admin_token: SecretStr
    daily_usd_cap: Decimal
    user_daily_questions: int
    # Read per question: ingest runs in its own process, so a value taken at startup goes stale.
    read_corpus_version: Callable[[], str]
    # Per IP per minute: with no login, the only control that separates one visitor from another.
    ip_rate_limit: int


def checkpoint_pool(database_url: str) -> ConnectionPool[Connection[DictRow]]:
    """Connection settings langgraph-checkpoint-postgres requires for a shared pool.

    database_url is the SQLAlchemy URL from Settings; psycopg wants it without the driver.
    """
    conninfo = make_url(database_url).set(drivername="postgresql")
    return ConnectionPool(
        conninfo.render_as_string(hide_password=False),
        connection_class=Connection[DictRow],
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )


@contextmanager
def open_runtime(settings: Settings, retrieve: Retriever) -> Iterator[AppRuntime]:
    engine = get_engine()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    llm = httpx.Client(
        base_url=settings.litellm_base_url,
        headers={"Authorization": f"Bearer {settings.litellm_api_key.get_secret_value()}"},
        # Longer than the proxy's worst case: strong, strong-fallback, fast and fast's own
        # fallback, 30 s each (config/litellm.yaml).
        timeout=130,
    )
    with checkpoint_pool(settings.database_url) as pool, llm, redis:
        checkpointer = PostgresSaver(pool, serde=CHECKPOINT_SERDE)
        checkpointer.setup()
        yield AppRuntime(
            agent=AgentContext(llm=llm, engine=engine, retrieve=retrieve),
            graph=build_graph(checkpointer),
            redis=redis,
            admin_token=settings.admin_token,
            daily_usd_cap=settings.daily_usd_cap,
            user_daily_questions=settings.user_daily_questions,
            read_corpus_version=partial(current_corpus_version, engine, settings.corpus_version),
            ip_rate_limit=settings.ip_rate_limit,
        )
    engine.dispose()


def get_runtime(request: Request) -> AppRuntime:
    runtime: AppRuntime = request.app.state.runtime
    return runtime
