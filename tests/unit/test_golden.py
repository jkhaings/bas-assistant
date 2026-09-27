"""Behaviour: the golden set is the table in data/top20_questions.md, grading holds each role
to what the table expects, and GET /evals/latest returns the newest run of each kind."""

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from bas_assistant.agent.turn import AskResponse, Citation
from bas_assistant.evals.golden import GoldenCase, grade, load_cases, parse_questions
from bas_assistant.evals.runs import record_run

pytestmark = pytest.mark.unit

ROOT = Path(__file__).parents[2]


def _case(number: int) -> GoldenCase:
    return next(case for case in load_cases(ROOT / "eval" / "golden.jsonl") if case.id == number)


def _response(decision: str, source_urls: list[str]) -> AskResponse:
    citations = [
        Citation(chunk_id="c", document_title="Doc", page=1, source_url=url, snippet="s")
        for url in source_urls
    ]
    return AskResponse.model_validate(
        {
            "answer": "text",
            "citations": citations,
            "decision": decision,
            "route": "fast",
            "model": "m",
            "request_id": uuid4(),
            "thread_id": uuid4(),
            "approval_required": False,
            "ticket_id": None,
            "notes": [],
            "cache_hit": False,
        }
    )


def test_golden_file_matches_the_question_table() -> None:
    table = parse_questions((ROOT / "data" / "top20_questions.md").read_text())

    assert table == load_cases(ROOT / "eval" / "golden.jsonl")
    assert len(table) == 20


def test_engineer_only_rows_are_asked_as_both_roles() -> None:
    assert _case(20).expect == {"support": "abstain", "engineer": "answer"}


def test_the_expected_source_is_the_product_key_of_the_catalog_sheet() -> None:
    assert _case(8).expected_source == "Red5-PLUS-1180"


def test_an_answer_citing_the_expected_document_passes() -> None:
    url = "https://deltacontrols.com/wp-content/uploads/Red5-PLUS-1180_Catalog-Sheet.pdf"

    assert grade(_case(8), "support", _response("answered", [url])).passed


def test_an_answer_citing_another_document_fails() -> None:
    url = "https://deltacontrols.com/wp-content/uploads/Red5-EDGE-1180_Catalog-Sheet.pdf"

    result = grade(_case(8), "support", _response("answered", [url]))

    assert not result.passed
    assert "Red5-PLUS-1180" in result.failure


def test_an_abstain_that_still_cites_fails() -> None:
    assert not grade(_case(16), "support", _response("abstained", ["https://x"])).passed


def test_latest_evals_returns_the_newest_run_of_each_kind(
    client: TestClient, engine: Engine
) -> None:
    record_run(engine, "golden", "1", {"golden": {"passed": 1}}, Decimal("0.01"))
    record_run(engine, "golden", "1", {"golden": {"passed": 2}}, Decimal("0.02"))

    body = client.get("/evals/latest").json()

    assert body["golden"]["scores"] == {"golden": {"passed": 2}}
    assert body["redteam"] is None
