"""The golden set: the twenty questions in data/top20_questions.md as cases to grade.

`python -m bas_assistant.evals.golden data/top20_questions.md eval/golden.jsonl` regenerates
the case file from the table.
"""

import re
import sys
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from bas_assistant.agent.turn import AskResponse

Expect = Literal["answer", "abstain"]

_ROW = re.compile(r"^\| (\d+) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$")
_NO_DOCUMENT = "—"


class GoldenCase(BaseModel):
    id: int
    question: str
    category: str
    # Matched case-insensitively inside a citation's source_url; None when the row must abstain.
    expected_source: str | None
    expected_page: int | None
    expected_fact: str
    # What each role asked must get. Support sees every public document engineer does, so
    # public rows are asked once, as support; engineer-only rows are asked as both.
    expect: dict[str, Expect]


class GoldenResult(BaseModel):
    case_id: int
    role: str
    category: str
    expect: Expect
    passed: bool
    failure: str
    # None when the request itself failed (a timeout or an HTTP error).
    request_id: UUID | None
    decision: str
    question: str
    answer: str
    reference: str
    cited: list[str]


def _expectations(category: str) -> dict[str, Expect]:
    if category == "out-of-scope":
        return {"support": "abstain"}
    if category == "engineer-only":
        return {"support": "abstain", "engineer": "answer"}
    return {"support": "answer"}


def _case(fields: list[str]) -> GoldenCase:
    number, question, category, document, page, fact = fields
    answerable = document != _NO_DOCUMENT
    return GoldenCase(
        id=int(number),
        question=question,
        category=category,
        # "Red5-PLUS-1180 Catalog Sheet" -> "Red5-PLUS-1180", which the PDF's file name and
        # the product page's slug both contain.
        expected_source=document.removesuffix(" Catalog Sheet").replace(" ", "-")
        if answerable
        else None,
        expected_page=int(page) if answerable else None,
        expected_fact=fact,
        expect=_expectations(category),
    )


def parse_questions(markdown: str) -> list[GoldenCase]:
    return [
        _case([field.strip() for field in match.groups()])
        for match in map(_ROW.match, markdown.splitlines())
        if match
    ]


def load_cases(path: Path) -> list[GoldenCase]:
    return [GoldenCase.model_validate_json(line) for line in path.read_text().splitlines()]


def _failure(case: GoldenCase, expect: Expect, response: AskResponse) -> str:
    """Why the response misses the case; empty when it passes."""
    cited = [citation.source_url for citation in response.citations]
    if expect == "abstain":
        if response.decision == "abstained" and not cited:
            return ""
        return f"expected an abstain, got {response.decision} citing {cited}"
    source = (case.expected_source or "").lower()
    if response.decision == "answered" and any(source in url.lower() for url in cited):
        return ""
    return (
        f"expected an answer citing {case.expected_source}, got {response.decision} citing {cited}"
    )


def grade(case: GoldenCase, role: str, response: AskResponse) -> GoldenResult:
    failure = _failure(case, case.expect[role], response)
    return GoldenResult(
        case_id=case.id,
        role=role,
        category=case.category,
        expect=case.expect[role],
        passed=not failure,
        failure=failure,
        request_id=response.request_id,
        decision=response.decision,
        question=case.question,
        answer=response.answer,
        reference=case.expected_fact,
        cited=[f"{c.document_title} p{c.page}" for c in response.citations],
    )


def request_failed(case: GoldenCase, role: str, error: str) -> GoldenResult:
    """A case whose request never produced an answer: it fails, and the run goes on."""
    return GoldenResult(
        case_id=case.id,
        role=role,
        category=case.category,
        expect=case.expect[role],
        passed=False,
        failure=f"request failed: {error}",
        request_id=None,
        decision="error",
        question=case.question,
        answer="",
        reference=case.expected_fact,
        cited=[],
    )


if __name__ == "__main__":
    table, out = (Path(arg) for arg in sys.argv[1:3])
    cases = parse_questions(table.read_text())
    out.write_text("".join(case.model_dump_json() + "\n" for case in cases))
