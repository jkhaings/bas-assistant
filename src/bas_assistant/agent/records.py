"""Rows for users, threads, requests and tickets touched by a graph turn."""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Engine, insert, select, update

from bas_assistant.agent.state import TicketDraft, UserContext
from bas_assistant.db import requests, threads, tickets, users
from bas_assistant.roles import Role

TicketStatus = Literal["proposed", "approved", "rejected", "filed"]


def demo_user_id(engine: Engine, role: Role) -> UUID:
    """The seeded demo user behind a "View as" role (service accounts have an api key)."""
    with engine.connect() as conn:
        user_id: UUID = conn.execute(
            select(users.c.id)
            .where(users.c.role == role, users.c.api_key_hash.is_(None))
            .order_by(users.c.created_at)
            .limit(1)
        ).scalar_one()
    return user_id


def create_thread(engine: Engine, user_id: UUID) -> UUID:
    thread_id = uuid4()
    with engine.begin() as conn:
        conn.execute(insert(threads).values(id=thread_id, user_id=user_id))
    return thread_id


def thread_owner(engine: Engine, thread_id: UUID) -> UUID | None:
    """The user who started the thread, or None if there is no such thread."""
    with engine.connect() as conn:
        owner: UUID | None = conn.execute(
            select(threads.c.user_id).where(threads.c.id == thread_id)
        ).scalar_one_or_none()
    return owner


def open_request(
    engine: Engine, request_id: UUID, thread_id: UUID, user: UserContext, question_redacted: str
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(requests).values(
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
    with engine.begin() as conn:
        conn.execute(update(requests).where(requests.c.id == request_id).values(asdict(outcome)))


def set_request_decision(engine: Engine, request_id: UUID, decision: str) -> None:
    with engine.begin() as conn:
        conn.execute(update(requests).where(requests.c.id == request_id).values(decision=decision))


def insert_ticket(engine: Engine, request_id: UUID, draft: TicketDraft) -> UUID:
    ticket_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            insert(tickets).values(
                id=ticket_id, request_id=request_id, draft=draft.model_dump(), status="proposed"
            )
        )
    return ticket_id


def set_ticket_status(
    engine: Engine, ticket_id: UUID, status: TicketStatus, approver_id: UUID
) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(tickets)
            .where(tickets.c.id == ticket_id)
            .values(status=status, approver_id=approver_id)
        )


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
        select(tickets, requests.c.thread_id)
        .join(requests, requests.c.id == tickets.c.request_id)
        .order_by(tickets.c.created_at.desc())
    )
    with engine.connect() as conn:
        rows = conn.execute(query).all()
    return [TicketOut.model_validate(row, from_attributes=True) for row in rows]
