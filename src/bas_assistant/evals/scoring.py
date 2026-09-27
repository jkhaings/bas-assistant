"""What a golden run records: judge-call metering, RAGAS means by category, the eval_runs
scores and the markdown summary. RAGAS itself runs in eval/ragas_run.py (dev only)."""

import math
import statistics
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel

from bas_assistant.agent.prompts import PROMPT_VERSION
from bas_assistant.evals.golden import GoldenResult
from bas_assistant.llm.gateway import Alias, Usage, parse_usage

METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
HEADINGS = ("Faithfulness", "Answer relevancy", "Context precision", "Context recall")

# Any: httpx's own type for an event-hook table.
EventHooks = dict[str, list[Callable[..., Any]]]

# One scored row per answered golden case: metric name -> score (NaN when the judge failed).
MetricRow = dict[str, float]


@dataclass
class JudgeMeter:
    """Reads the proxy's model id and cost headers off every judge response."""

    calls: list[Usage] = field(default_factory=list)

    def on_request(self, request: httpx.Request) -> None:
        request.extensions["judge_started"] = time.perf_counter()

    async def aon_request(self, request: httpx.Request) -> None:
        self.on_request(request)

    def _record(self, response: httpx.Response) -> None:
        if not response.is_success:
            return
        alias: Alias = "embed" if response.request.url.path.endswith("/embeddings") else "fast"
        started: float = response.request.extensions["judge_started"]
        latency_ms = round((time.perf_counter() - started) * 1000)
        self.calls.append(parse_usage(alias, response, latency_ms))

    def on_response(self, response: httpx.Response) -> None:
        response.read()
        self._record(response)

    async def aon_response(self, response: httpx.Response) -> None:
        await response.aread()
        self._record(response)

    def event_hooks(self) -> EventHooks:
        return {"request": [self.on_request], "response": [self.on_response]}

    def async_event_hooks(self) -> EventHooks:
        return {"request": [self.aon_request], "response": [self.aon_response]}

    def usd(self) -> Decimal:
        return sum((call.usd for call in self.calls), Decimal(0))


class CategoryScores(BaseModel):
    n: int
    faithfulness: float | None
    answer_relevancy: float | None
    context_precision: float | None
    context_recall: float | None


class GoldenSummary(BaseModel):
    passed: int
    total: int
    rate: float


class GoldenRunScores(BaseModel):
    """The eval_runs.scores document of a golden run. Session D's Quality & adoption
    dashboard reads the RAGAS means from `overall` and `by_category`."""

    run_at: str
    corpus_version: str
    golden: GoldenSummary
    failures: dict[str, str]
    overall: CategoryScores
    by_category: dict[str, CategoryScores]


def mean(values: list[float]) -> float | None:
    # A judge call that failed leaves NaN; the mean is over the rows that were scored.
    scored = [value for value in values if not math.isnan(value)]
    return round(statistics.fmean(scored), 3) if scored else None


def category_scores(rows: list[MetricRow]) -> CategoryScores:
    """The mean of each metric over the rows, and how many rows there were."""
    return CategoryScores(
        n=len(rows), **{metric: mean([row[metric] for row in rows]) for metric in METRICS}
    )


def by_category(answered: list[GoldenResult], rows: list[MetricRow]) -> dict[str, CategoryScores]:
    groups: dict[str, list[MetricRow]] = defaultdict(list)
    for result, row in zip(answered, rows, strict=True):
        groups[result.category].append(row)
    return {category: category_scores(group) for category, group in sorted(groups.items())}


def summarize(results: list[GoldenResult]) -> GoldenSummary:
    passed = sum(result.passed for result in results)
    return GoldenSummary(passed=passed, total=len(results), rate=passed / len(results))


def _results_table(results: list[GoldenResult]) -> list[str]:
    return [
        "| # | Role | Category | Expect | Decision | Result |",
        "|---|---|---|---|---|---|",
        *(
            f"| {r.case_id} | {r.role} | {r.category} | {r.expect} | {r.decision} | "
            f"{'pass' if r.passed else 'FAIL: ' + r.failure} |"
            for r in results
        ),
    ]


def _ragas_table(scores: GoldenRunScores) -> list[str]:
    lines = ["| Category | n | " + " | ".join(HEADINGS) + " |", "|---|---|" + "---|" * 4]
    for category, row in [*scores.by_category.items(), ("overall", scores.overall)]:
        values = [getattr(row, metric) for metric in METRICS]
        cells = ["—" if value is None else f"{value:.3f}" for value in values]
        lines.append(f"| {category} | {row.n} | " + " | ".join(cells) + " |")
    return lines


def summary_markdown(
    scores: GoldenRunScores, results: list[GoldenResult], answers_usd: Decimal, judge_usd: Decimal
) -> str:
    golden = scores.golden
    lines = [
        f"# Golden set and RAGAS, {scores.run_at}",
        "",
        f"Corpus version `{scores.corpus_version}`, prompt version `{PROMPT_VERSION}`. "
        f"Cost ${answers_usd + judge_usd:.4f} "
        f"(answers ${answers_usd:.4f}, RAGAS judge ${judge_usd:.4f}).",
        "",
        f"## Golden pass rate: {golden.passed}/{golden.total} ({golden.rate:.0%})",
        "",
        *_results_table(results),
        "",
        "## RAGAS by category (answered rows; judge = `fast` alias)",
        "",
        *_ragas_table(scores),
    ]
    return "\n".join(lines) + "\n"
