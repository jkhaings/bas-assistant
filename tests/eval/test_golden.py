"""The golden set against the running stack: each question of data/top20_questions.md must
cite its expected document or abstain as the table says. Writes eval/results/golden-latest.jsonl
for eval/ragas_run.py (`make eval`; never in CI).
"""

import os
from pathlib import Path

import httpx
import pytest
from redis import Redis

from bas_assistant.agent.prompts import PROMPT_VERSION
from bas_assistant.agent.turn import AskResponse
from bas_assistant.cost.cache import cache_key
from bas_assistant.db.corpus import current_corpus_version
from bas_assistant.db.engine import get_engine
from bas_assistant.evals.golden import (
    GoldenCase,
    GoldenResult,
    grade,
    load_cases,
    request_failed,
)
from bas_assistant.settings import Settings

pytestmark = pytest.mark.eval

EVAL_DIR = Path(__file__).parents[2] / "eval"
RESULTS = EVAL_DIR / "results" / "golden-latest.jsonl"
CASES = load_cases(EVAL_DIR / "golden.jsonl")
RUNS = [(case, role) for case in CASES for role in case.expect]


def _run_case(
    app: httpx.Client, redis: Redis, version: str, case: GoldenCase, role: str
) -> GoldenResult:
    # A cached answer would grade an earlier run, not the current prompts and corpus.
    redis.delete(cache_key(case.question, role, version, PROMPT_VERSION))
    try:
        response = app.post("/ask", json={"question": case.question}, headers={"X-Demo-Role": role})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        # One slow or refused request fails its own case, not the other 21.
        return request_failed(case, role, repr(exc))
    return grade(case, role, AskResponse.model_validate(response.json()))


@pytest.fixture(scope="module")
def results(app: httpx.Client) -> dict[tuple[int, str], GoldenResult]:
    # Emptied first: a run that stops early must leave eval/ragas_run.py nothing to score, not
    # the previous run's results.
    RESULTS.write_text("")
    # An empty corpus abstains on every question, which reads as a retrieval failure. Engineer
    # sees every ACL group, so no documents means nothing was ingested.
    documents = app.get("/documents", headers={"X-Demo-Role": "engineer"})
    documents.raise_for_status()
    if not documents.json():
        pytest.exit("The app's corpus is empty: run `make ingest`, then `make eval`.", returncode=1)
    version = current_corpus_version(get_engine(), Settings().corpus_version)
    with Redis.from_url(os.environ["REDIS_URL"]) as redis:
        graded = {
            (case.id, role): _run_case(app, redis, version, case, role) for case, role in RUNS
        }
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text("".join(result.model_dump_json() + "\n" for result in graded.values()))
    return graded


@pytest.mark.parametrize(
    ("case_id", "role"),
    [(case.id, role) for case, role in RUNS],
    ids=[f"{case.id:02d}-{case.category}-{role}" for case, role in RUNS],
)
def test_golden_case(results: dict[tuple[int, str], GoldenResult], case_id: int, role: str) -> None:
    result = results[(case_id, role)]
    assert result.passed, result.failure
