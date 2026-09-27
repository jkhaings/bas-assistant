"""Behaviour: every judge call is metered from the proxy's headers, RAGAS means skip failed
judgements, and eval/ragas_run.py imports cleanly in the locked environment."""

import importlib.util
import math
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from bas_assistant.evals.golden import GoldenResult
from bas_assistant.evals.scoring import (
    METRICS,
    GoldenRunScores,
    JudgeMeter,
    by_category,
    category_scores,
    mean,
    summarize,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).parents[2]


def _proxy(request: httpx.Request) -> httpx.Response:
    headers = {"x-litellm-model-id": "openai/gpt-4o-mini", "x-litellm-response-cost": "0.00012"}
    usage = {"prompt_tokens": 50, "completion_tokens": 10}
    if request.url.path.endswith("/embeddings"):
        return httpx.Response(200, json={"data": [], "usage": usage}, headers=headers)
    if b"fail" in request.content:
        return httpx.Response(500, json={"error": {"message": "down"}})
    return httpx.Response(200, json={"choices": [], "usage": usage}, headers=headers)


def test_each_successful_judge_call_is_metered_with_its_alias_and_cost() -> None:
    meter = JudgeMeter()
    transport = httpx.MockTransport(_proxy)
    with httpx.Client(transport=transport, event_hooks=meter.event_hooks()) as client:
        client.post("http://proxy/v1/chat/completions", json={"model": "fast"})
        client.post("http://proxy/v1/embeddings", json={"model": "embed"})
        client.post("http://proxy/v1/chat/completions", json={"model": "fast", "x": "fail"})

    assert [(call.alias, call.model, call.input_tokens) for call in meter.calls] == [
        ("fast", "gpt-4o-mini", 50),
        ("embed", "gpt-4o-mini", 50),
    ]
    assert meter.usd() == Decimal("0.00024")


def _result(category: str) -> GoldenResult:
    return GoldenResult(
        case_id=1,
        role="support",
        category=category,
        expect="answer",
        passed=True,
        failure="",
        request_id=uuid4(),
        decision="answered",
        question="q",
        answer="a",
        reference="r",
        cited=[],
    )


def test_a_failed_judgement_is_left_out_of_the_mean() -> None:
    assert mean([0.5, math.nan, 1.0]) == 0.75
    assert mean([math.nan]) is None


def test_scores_are_grouped_by_category_with_the_overall_mean_apart() -> None:
    row = {"faithfulness": 1.0, "answer_relevancy": 0.5, "context_precision": 0.0}
    rows = [row | {"context_recall": 1.0}, row | {"context_recall": 0.0}]

    groups = by_category([_result("spec"), _result("protocol")], rows)
    overall = category_scores(rows)

    assert sorted(groups) == ["protocol", "spec"]
    assert groups["spec"].context_recall == 1.0
    assert (overall.n, overall.context_recall) == (2, 0.5)


def test_the_ragas_runner_imports_in_the_locked_environment() -> None:
    # RAGAS imports LangChain modules that move between releases; this catches a bad lock.
    spec = importlib.util.spec_from_file_location("ragas_run", ROOT / "eval" / "ragas_run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert callable(module.main)


def test_the_stored_scores_have_the_shape_the_quality_dashboard_reads() -> None:
    rows = [dict.fromkeys(METRICS, 1.0)]
    scores = GoldenRunScores(
        run_at="2026-09-27T12:00:00+00:00",
        corpus_version="1",
        golden=summarize([_result("spec")]),
        failures={},
        overall=category_scores(rows),
        by_category=by_category([_result("spec")], rows),
    ).model_dump()

    assert set(METRICS) < set(scores["overall"])
    assert set(METRICS) < set(scores["by_category"]["spec"])
