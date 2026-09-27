"""POST /search: hybrid retrieval with citations and no model answer (session A's /ask).

POST /ask is the agent graph (agent/api.py); this keeps retrieval inspectable on its own.
"""

from __future__ import annotations

import time
import uuid
from functools import lru_cache, partial

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from bas_assistant.api.roles import Role, acl_groups_for_role, demo_role
from bas_assistant.db.activity import Request, RequestChunk, Thread, Usage, User
from bas_assistant.db.engine import get_session
from bas_assistant.guardrails.input import redact
from bas_assistant.guardrails.limits import per_ip_limit
from bas_assistant.retrieval.embeddings import OpenAIEmbedder
from bas_assistant.retrieval.pipeline import (
    Citation,
    RetrievalDeps,
    RetrievalResult,
    RetrievedChunk,
    Timings,
    retrieve,
)
from bas_assistant.retrieval.rerank import rerank
from bas_assistant.retrieval.store import PgVectorStore
from bas_assistant.settings import Settings

router = APIRouter()


class AskRequest(BaseModel):
    """POST /ask body."""

    question: str
    # Part of the contract in docs/SESSIONS.md's session A spec; not yet wired
    # to a product/doc_type filter in retrieve() — accepted so the request
    # shape doesn't change when a later session adds that.
    filters: dict[str, str] | None = None


class AskResponse(BaseModel):
    """POST /ask response."""

    request_id: uuid.UUID
    answer: None = None
    citations: list[Citation]
    retrieved: list[RetrievedChunk]
    abstained: bool
    timings: Timings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read environment settings once per process."""
    return Settings()


def get_retrieval_deps(
    session: Session = Depends(get_session), settings: Settings = Depends(get_settings)
) -> RetrievalDeps:
    """Build the retrieval pipeline's infrastructure for one request."""
    return RetrievalDeps(
        embedder=OpenAIEmbedder(settings),
        store=PgVectorStore(session),
        reranker=partial(rerank, settings.rerank_model),
        rerank_threshold=settings.rerank_threshold,
    )


def _demo_user(session: Session, role: Role) -> User:
    """The seeded demo user for this role (see migration 0001)."""
    return session.scalars(select(User).where(User.role == role.value)).one()


def _create_request(
    session: Session, role: Role, question_redacted: str, decision: str, latency_ms: int
) -> Request:
    user = _demo_user(session, role)
    thread = Thread(user_id=user.id)
    session.add(thread)
    session.flush()

    request = Request(
        thread_id=thread.id,
        user_id=user.id,
        role=role.value,
        question_redacted=question_redacted,
        decision=decision,
        latency_ms=latency_ms,
    )
    session.add(request)
    session.flush()
    return request


def _record_result(
    session: Session, request: Request, result: RetrievalResult, embed_model: str
) -> None:
    session.add_all(
        RequestChunk(request_id=request.id, chunk_id=item.chunk_id, rank=rank, score=item.score)
        for rank, item in enumerate(result.retrieved, start=1)
    )
    provider, model = result.embed_usage.provider_and_model(embed_model)
    session.add(
        Usage(
            request_id=request.id,
            stage="embed",
            alias="embed",
            model=model,
            provider=provider,
            input_tokens=result.embed_usage.input_tokens,
            usd=result.embed_usage.usd,
            latency_ms=result.embed_usage.latency_ms,
        )
    )
    session.commit()


@router.post("/search", response_model=AskResponse, dependencies=[Depends(per_ip_limit)])
def ask(
    body: AskRequest,
    role: Role = Depends(demo_role),
    session: Session = Depends(get_session),
    deps: RetrievalDeps = Depends(get_retrieval_deps),
) -> AskResponse:
    """Retrieve citations for a question. Abstains when nothing scores above threshold."""
    start = time.monotonic()
    # The query embedding is a model call too: it gets the redacted question, never the raw one.
    question = redact(body.question).text
    result = retrieve(question, acl_groups_for_role(role), deps)
    latency_ms = int((time.monotonic() - start) * 1000)

    decision = "abstained" if result.abstained else "retrieved"
    request = _create_request(session, role, question, decision, latency_ms)
    _record_result(session, request, result, deps.embedder.model)

    return AskResponse(
        request_id=request.id,
        citations=result.citations,
        retrieved=result.retrieved,
        abstained=result.abstained,
        timings=result.timings,
    )
