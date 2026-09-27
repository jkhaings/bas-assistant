"""POST /requests/{id}/feedback ("used without edits") and /flag ("sounded right but wasn't")."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Engine, delete, insert, select

from bas_assistant.agent.api import Runtime, current_user
from bas_assistant.agent.state import UserContext
from bas_assistant.db.activity import Feedback, Flag, Request
from bas_assistant.guardrails.input import redact
from bas_assistant.observability.metrics import FEEDBACK, FLAGS

router = APIRouter()

Caller = Annotated[UserContext, Depends(current_user)]


class FeedbackBody(BaseModel):
    value: Literal["used_as_is", "used_with_edits", "not_used"]


class FlagBody(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


def _check_owner(engine: Engine, request_id: UUID, user: UserContext) -> None:
    # Another role's request is reported as missing, like another role's thread.
    with engine.connect() as conn:
        owner = conn.execute(
            select(Request.user_id).where(Request.id == request_id)
        ).scalar_one_or_none()
    if owner != user.id:
        raise HTTPException(404, detail="request not found")


@router.post("/requests/{request_id}/feedback", status_code=204)
def give_feedback(request_id: UUID, body: FeedbackBody, user: Caller, runtime: Runtime) -> None:
    engine = runtime.agent.engine
    _check_owner(engine, request_id, user)
    with engine.begin() as conn:
        # One vote per person per answer: clicking another button changes it.
        conn.execute(
            delete(Feedback).where(Feedback.request_id == request_id, Feedback.user_id == user.id)
        )
        conn.execute(
            insert(Feedback).values(request_id=request_id, user_id=user.id, value=body.value)
        )
    FEEDBACK.labels(body.value).inc()


@router.post("/requests/{request_id}/flag", status_code=204)
def flag_answer(request_id: UUID, body: FlagBody, user: Caller, runtime: Runtime) -> None:
    engine = runtime.agent.engine
    _check_owner(engine, request_id, user)
    # Presidio, as for the question: the reason is free text from a public page.
    with engine.begin() as conn:
        conn.execute(
            insert(Flag).values(
                request_id=request_id, reviewer_id=user.id, reason=redact(body.reason).text
            )
        )
    FLAGS.inc()
