"""Rows for users, threads, requests, request_chunks and tickets touched by a graph turn."""

import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Engine, insert, select, update

from bas_assistant.agent.state import Passage, TicketDraft, UserContext
from bas_assistant.db.activity import Request, RequestChunk, Thread, Ticket, User
from bas_assistant.observability.metrics import TICKETS, observe_request

TicketStatus = Literal["proposed", "approved", "rejected", "filed"]


def demo_user_id(engine: Engine, role: str) -> UUID:
    """The seeded demo user behind a "View as" role (service accounts have an api key)."""
    with engine.connect() as conn:
        user_id: UUID = conn.execute(
            select(User.id)
            .where(User.role == role, User.api_key_hash.is_(None))
            .order_by(User.created_at)
            .limit(1)
        ).scalar_one()
    return user_id


def create_thread(engine: Engine, user_id: UUID) -> UUID:
    thread_id = uuid4()
    with engine.begin() as conn:
        conn.execute(insert(Thread).values(id=thread_id, user_id=user_id))
    return thread_id


def thread_owner(engine: Engine, thread_id: UUID) -> UUID | None:
    """The user who started the thread, or None if there is no such thread."""
    with engine.connect() as conn:
        owner: UUID | None = conn.execute(
            select(Thread.user_id).where(Thread.id == thread_id)
        ).scalar_one_or_none()
    return owner


def open_request(
    engine: Engine, request_id: UUID, thread_id: UUID, user: UserContext, question_redacted: str
) -> None:
    """The row exists while the graph runs; decision and latency are set when it closes."""
    with engine.begin() as conn:
        conn.execute(
            insert(Request).values(
                id=request_id,
                thread_id=thread_id,
                user_id=user.id,
                role=user.role,
                question_redacted=question_redacted,
            )
        )


@dataclass(frozen=True)
class RequestOutcome:
    route: str | None
    decision: str
    latency_ms: int
    retrieval_ms: int
    rerank_ms: int


def close_request(engine: Engine, request_id: UUID, outcome: RequestOutcome) -> None:
    """Every request closes here (graph, cache hit, or outage), so it is also counted here."""
    with engine.begin() as conn:
        conn.execute(update(Request).where(Request.id == request_id).values(asdict(outcome)))
    observe_request(outcome.route, outcome.decision, outcome.latency_ms)


def set_request_decision(engine: Engine, request_id: UUID, decision: str) -> None:
    with engine.begin() as conn:
        conn.execute(update(Request).where(Request.id == request_id).values(decision=decision))


def record_request_chunks(
    engine: Engine, request_id: UUID, passages: list[Passage], cited: list[str]
) -> None:
    """What was retrieved for the request, in rank order, and which passages were cited."""
    if not passages:
        return
    rows = [
        {
            "request_id": request_id,
            "chunk_id": uuid.UUID(passage.chunk_id),
            "rank": rank,
            "score": passage.score,
            "used_in_answer": passage.chunk_id in cited,
        }
        for rank, passage in enumerate(passages, start=1)
    ]
    with engine.begin() as conn:
        conn.execute(insert(RequestChunk), rows)


def insert_ticket(engine: Engine, request_id: UUID, draft: TicketDraft) -> UUID:
    ticket_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            insert(Ticket).values(
                id=ticket_id,
                request_id=request_id,
                draft=draft.model_dump(),
                status="proposed",
                created_at=datetime.now(UTC),
            )
        )
    TICKETS.labels("proposed").inc()
    return ticket_id


def set_ticket_status(
    engine: Engine, ticket_id: UUID, status: TicketStatus, approver_id: UUID
) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .values(status=status, approver_id=approver_id)
        )
    TICKETS.labels(status).inc()


class TicketOut(BaseModel):
    id: UUID
    request_id: UUID
    thread_id: UUID
    status: TicketStatus
    draft: TicketDraft
    approver_id: UUID | None
    created_at: datetime


def list_tickets(engine: Engine) -> list[TicketOut]:
    query = (
        select(
            Ticket.id,
            Ticket.request_id,
            Request.thread_id,
            Ticket.status,
            Ticket.draft,
            Ticket.approver_id,
            Ticket.created_at,
        )
        .join(Request, Request.id == Ticket.request_id)
        .order_by(Ticket.created_at.desc())
    )
    with engine.connect() as conn:
        rows = conn.execute(query).all()
    return [TicketOut.model_validate(row, from_attributes=True) for row in rows]
