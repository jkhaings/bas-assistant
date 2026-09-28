"""Red-team fixtures against the running stack, and the eval_runs row (kind redteam) the
Evals tab reads: one per `make redteam`, with each case's outcome and the run's model spend."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from redis import Redis
from sqlalchemy import Engine, func, select

from bas_assistant.db.activity import Usage
from bas_assistant.db.corpus import current_corpus_version
from bas_assistant.db.engine import get_engine
from bas_assistant.evals.runs import record_run
from bas_assistant.settings import Settings

APP_URL = "http://localhost:8000"

_STARTED = datetime.now(UTC)
_OUTCOMES: dict[str, str] = {}


@pytest.fixture(scope="session")
def app() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=APP_URL, timeout=180) as client:
        yield client


@pytest.fixture(scope="session")
def engine() -> Engine:
    return get_engine()


@pytest.fixture(scope="session")
def redis() -> Iterator[Redis]:
    with Redis.from_url(os.environ["REDIS_URL"]) as client:
        yield client


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    # A failure in setup counts against the case as much as a failure in the test body.
    if report.when == "call" or report.outcome == "failed":
        _OUTCOMES[report.nodeid.rsplit("::", 1)[-1]] = report.outcome


def pytest_sessionfinish() -> None:
    # Unit runs collect this directory too and deselect every case: nothing to record.
    if not _OUTCOMES:
        return
    engine = get_engine()
    with engine.connect() as conn:
        spent: Decimal = conn.execute(
            select(func.coalesce(func.sum(Usage.usd), 0)).where(Usage.created_at >= _STARTED)
        ).scalar_one()
    passed = sum(outcome == "passed" for outcome in _OUTCOMES.values())
    scores: dict[str, object] = {
        "run_at": _STARTED.isoformat(timespec="seconds"),
        "passed": passed,
        "total": len(_OUTCOMES),
        "cases": dict(_OUTCOMES),
    }
    version = current_corpus_version(engine, Settings().corpus_version)
    record_run(engine, "redteam", version, scores, Decimal(spent))
