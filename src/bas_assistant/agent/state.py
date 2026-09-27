"""Typed graph state (docs/ARCHITECTURE.md section 5) and the model's structured output."""

import operator
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from bas_assistant.llm.router import Route
from bas_assistant.roles import Role

Decision = Literal["answered", "abstained", "refused", "paused", "failed"]
Approval = Literal["none", "pending", "approved", "rejected"]


class Passage(BaseModel):
    chunk_id: str
    document_title: str
    page: int
    source_url: str
    text: str
    score: float


@dataclass(frozen=True)
class Retrieval:
    passages: list[Passage]
    retrieval_ms: int
    rerank_ms: int


# (question, acl_groups) -> passages the role may see. Session A's VectorStore plugs in here.
Retriever = Callable[[str, list[str]], Retrieval]


class TicketDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    body: str


class AnswerOut(BaseModel):
    """Structured output of the answer call. Every field is required for strict JSON schema."""

    model_config = ConfigDict(extra="forbid")

    # False when the passages do not answer the question: the graph abstains instead.
    answerable: bool
    answer: str
    citations: list[str]
    confidence: Literal["low", "medium", "high"]
    needs_ticket: bool
    ticket_draft: TicketDraft | None


class ApprovalVerdict(BaseModel):
    approve: bool
    approver_id: UUID


class UserContext(BaseModel):
    id: UUID
    role: Role
    acl_groups: list[str]
    tools_allowed: list[str]


class Turn(BaseModel):
    question: str
    answer: str


class AgentState(BaseModel):
    request_id: UUID
    question: str
    user: UserContext
    route: Route | None = None
    topic: str = ""
    retrieved: list[Passage] = []
    retrieval_ms: int = 0
    rerank_ms: int = 0
    draft_raw: str = ""
    draft: AnswerOut | None = None
    answer_model: str | None = None
    attempts: int = 0
    validation_errors: list[str] = []
    ticket_id: UUID | None = None
    approval: Approval = "none"
    approver_id: UUID | None = None
    decision: Decision | None = None
    final_answer: str = ""
    notes: list[str] = []
    # Accumulates across turns of a thread; every other field is reset per turn.
    history: Annotated[list[Turn], operator.add] = []


def turn_input(request_id: UUID, question: str, user: UserContext) -> AgentState:
    """Graph input for a new turn.

    LangGraph writes only the input fields in model_fields_set or not None, so the
    round trip marks every per-turn field as set and the previous turn's values reset.
    History is left out and keeps accumulating through its reducer.
    """
    fresh = AgentState(request_id=request_id, question=question, user=user)
    return AgentState.model_validate(fresh.model_dump(exclude={"history"}))
