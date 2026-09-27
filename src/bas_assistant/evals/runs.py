"""eval_runs rows: one per golden or red-team run, newest read back for the UI."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Engine, insert, select

from bas_assistant.agent.prompts import PROMPT_VERSION
from bas_assistant.db.activity import EvalRun

RunKind = Literal["golden", "redteam"]


class EvalRunOut(BaseModel):
    id: UUID
    kind: RunKind
    corpus_version: str
    prompt_version: str
    scores: dict[str, object]
    cost_usd: Decimal
    created_at: datetime


class LatestRuns(BaseModel):
    golden: EvalRunOut | None
    redteam: EvalRunOut | None


def record_run(
    engine: Engine, kind: RunKind, corpus_version: str, scores: dict[str, object], cost: Decimal
) -> UUID:
    with engine.begin() as conn:
        run_id: UUID = conn.execute(
            insert(EvalRun)
            .values(
                kind=kind,
                corpus_version=corpus_version,
                prompt_version=PROMPT_VERSION,
                scores=scores,
                cost_usd=cost,
                # Explicit so two runs in the same second still order correctly.
                created_at=datetime.now(UTC),
            )
            .returning(EvalRun.id)
        ).scalar_one()
    return run_id


def _latest(engine: Engine, kind: RunKind) -> EvalRunOut | None:
    query = select(EvalRun).where(EvalRun.kind == kind).order_by(EvalRun.created_at.desc())
    with engine.connect() as conn:
        row = conn.execute(query.limit(1)).first()
    return None if row is None else EvalRunOut.model_validate(row, from_attributes=True)


def latest_runs(engine: Engine) -> LatestRuns:
    return LatestRuns(golden=_latest(engine, "golden"), redteam=_latest(engine, "redteam"))
