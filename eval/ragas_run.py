"""RAGAS over the latest golden run (eval/results/golden-latest.jsonl, written by
tests/eval/test_golden.py): faithfulness, answer relevancy, context precision and context
recall, overall and by category.

The judge is the `fast` alias and the embeddings the `embed` alias, both through the LiteLLM
proxy with the app's virtual key; every judge call is metered as a `usage` row (stage judge).
Writes an eval_runs row and eval/results/latest.md. Dev only (`make eval`): RAGAS and
langchain-openai are not in the app image.
"""

import logging
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import EvaluationDataset, RunConfig, evaluate
from ragas.dataset_schema import EvaluationResult
from ragas.embeddings.base import LangchainEmbeddingsWrapper
from ragas.llms.base import LangchainLLMWrapper
from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness
from sqlalchemy import Engine, func, select

from bas_assistant.cost.usage import record_usage
from bas_assistant.db.activity import RequestChunk, Usage
from bas_assistant.db.corpus import Chunk, Parent
from bas_assistant.db.engine import get_engine
from bas_assistant.evals.golden import GoldenResult
from bas_assistant.evals.runs import record_run
from bas_assistant.evals.scoring import (
    METRICS,
    GoldenRunScores,
    JudgeMeter,
    MetricRow,
    by_category,
    category_scores,
    summarize,
    summary_markdown,
)
from bas_assistant.logging import configure_logging
from bas_assistant.settings import Settings

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"


def _clients(meter: JudgeMeter) -> dict[str, Any]:
    # Any: langchain-openai takes its httpx clients as untyped keyword arguments.
    return {
        "http_client": httpx.Client(timeout=120, event_hooks=meter.event_hooks()),
        "http_async_client": httpx.AsyncClient(timeout=120, event_hooks=meter.async_event_hooks()),
    }


def _judges(
    settings: Settings, meter: JudgeMeter
) -> tuple[LangchainLLMWrapper, LangchainEmbeddingsWrapper]:
    base_url = f"{settings.litellm_base_url}/v1"
    key = settings.litellm_api_key
    chat = ChatOpenAI(
        model_name="fast",
        openai_api_base=base_url,
        openai_api_key=key,
        temperature=0,
        **_clients(meter),
    )
    embeddings = OpenAIEmbeddings(
        model="embed",
        openai_api_base=base_url,
        openai_api_key=key,
        # "embed" is a proxy alias, not a model tiktoken knows; the proxy handles length.
        check_embedding_ctx_length=False,
        **_clients(meter),
    )
    return LangchainLLMWrapper(chat), LangchainEmbeddingsWrapper(embeddings)


def _contexts(engine: Engine, request_id: UUID | None) -> list[str]:
    """The parents the answer model read for the request, in rank order."""
    query = (
        select(Parent.text)
        .join(Chunk, Chunk.parent_id == Parent.id)
        .join(RequestChunk, RequestChunk.chunk_id == Chunk.id)
        .where(RequestChunk.request_id == request_id)
        .order_by(RequestChunk.rank)
    )
    with engine.connect() as conn:
        return list(conn.execute(query).scalars())


def _score(
    answered: list[GoldenResult], engine: Engine, settings: Settings, meter: JudgeMeter
) -> list[MetricRow]:
    dataset = EvaluationDataset.from_list(
        [
            {
                "user_input": result.question,
                "response": result.answer,
                "retrieved_contexts": _contexts(engine, result.request_id),
                "reference": result.reference,
            }
            for result in answered
        ]
    )
    llm, embeddings = _judges(settings, meter)
    result = evaluate(
        dataset,
        metrics=[Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()],
        llm=llm,
        embeddings=embeddings,
        run_config=RunConfig(max_workers=4, timeout=180),
        show_progress=False,
    )
    assert isinstance(result, EvaluationResult), "evaluate() returns an Executor only on request"
    # RAGAS types its rows as dict[str, Any]; the four metrics are floats (NaN on a judge error).
    return [{metric: float(row[metric]) for metric in METRICS} for row in result.scores]


def _answers_usd(engine: Engine, results: list[GoldenResult]) -> Decimal:
    ids = [result.request_id for result in results if result.request_id is not None]
    with engine.connect() as conn:
        total: Decimal = conn.execute(
            select(func.coalesce(func.sum(Usage.usd), 0)).where(Usage.request_id.in_(ids))
        ).scalar_one()
    return Decimal(total)


def main() -> None:
    # RAGAS posts usage telemetry to its vendor unless this is set; it reads it on first use.
    os.environ["RAGAS_DO_NOT_TRACK"] = "true"
    configure_logging()
    settings, engine, meter = Settings(), get_engine(), JudgeMeter()
    lines = (RESULTS_DIR / "golden-latest.jsonl").read_text().splitlines()
    results = [GoldenResult.model_validate_json(line) for line in lines]
    answered = [result for result in results if result.decision == "answered"]
    try:
        rows = _score(answered, engine, settings, meter)
    finally:
        # Spend is real even when RAGAS fails halfway; the daily cap has to see it.
        for call in meter.calls:
            record_usage(engine, None, "judge", call)
    scores = GoldenRunScores(
        run_at=datetime.now(UTC).isoformat(timespec="seconds"),
        corpus_version=settings.corpus_version,
        golden=summarize(results),
        failures={f"{r.case_id}-{r.role}": r.failure for r in results if not r.passed},
        overall=category_scores(rows),
        by_category=by_category(answered, rows),
    )
    answers_usd = _answers_usd(engine, results)
    run_id = record_run(
        engine, "golden", settings.corpus_version, scores.model_dump(), answers_usd + meter.usd()
    )
    summary = summary_markdown(scores, results, answers_usd, meter.usd())
    (RESULTS_DIR / "latest.md").write_text(summary)
    logger.info("eval run %s: %s", run_id, scores.golden.model_dump_json())


if __name__ == "__main__":
    main()
