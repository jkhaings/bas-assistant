"""HTTP surface of the agent: ask, stream, approve, thread history, tickets."""

import secrets
from collections.abc import Iterator
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langgraph.types import Command
from pydantic import BaseModel, Field

from bas_assistant.agent.records import (
    TicketOut,
    demo_user_id,
    list_tickets,
    set_request_decision,
    thread_owner,
)
from bas_assistant.agent.state import AgentState, ApprovalVerdict, Turn, UserContext
from bas_assistant.agent.turn import (
    AskResponse,
    OpenTurn,
    close_turn,
    fail_turn,
    invoke_graph,
    open_turn,
    serve_from_cache,
    stream_graph,
    thread_config,
)
from bas_assistant.api.roles import Role, acl_groups_for_role, demo_role, tools_for_role
from bas_assistant.audit import write_audit
from bas_assistant.guardrails.limits import limit_detail, limit_error, per_ip_limit
from bas_assistant.llm.gateway import GatewayError, KeyBudgetError
from bas_assistant.observability.tracing import record_event, tag_trace
from bas_assistant.runtime import AppRuntime, get_runtime

router = APIRouter()

Runtime = Annotated[AppRuntime, Depends(get_runtime)]


def current_user(role: Annotated[Role, Depends(demo_role)], runtime: Runtime) -> UserContext:
    return UserContext(
        id=demo_user_id(runtime.agent.engine, role.value),
        role=role.value,
        acl_groups=acl_groups_for_role(role),
        tools_allowed=tools_for_role(role),
    )


def require_admin(runtime: Runtime, x_admin_token: Annotated[str, Header()] = "") -> None:
    expected = runtime.admin_token.get_secret_value().encode()
    if not secrets.compare_digest(x_admin_token.encode(), expected):
        raise HTTPException(401, detail="admin token required")


def require_approver(role: Annotated[Role, Depends(demo_role)], runtime: Runtime) -> None:
    """The token alone is not enough: the role in the switcher must hold the approve tool."""
    if "approve_ticket" in tools_for_role(role):
        return
    write_audit(
        runtime.agent.engine,
        None,
        actor=role.value,
        action="approve_refused",
        detail={"reason": "role lacks approve_ticket"},
    )
    raise HTTPException(403, detail="this role cannot approve tickets")


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    thread_id: UUID | None = None


def start_turn(
    body: AskBody, user: Annotated[UserContext, Depends(current_user)], runtime: Runtime
) -> OpenTurn:
    return open_turn(runtime, body.question, body.thread_id, user)


Started = Annotated[OpenTurn, Depends(start_turn)]


# The rate limit runs before start_turn, so a rejected request writes no request row.
@router.post("/ask", dependencies=[Depends(per_ip_limit)])
def ask(turn: Started, runtime: Runtime) -> AskResponse:
    if turn.cached is not None:
        return serve_from_cache(runtime, turn, turn.cached)
    try:
        invoke_graph(runtime, turn)
    except KeyBudgetError as exc:
        fail_turn(runtime, turn, "key budget reached")
        raise limit_error(429, "key_budget_reached", None) from exc
    except GatewayError as exc:
        fail_turn(runtime, turn, "model unavailable")
        raise limit_error(503, "model_unavailable", None) from exc
    except Exception:
        # Any other error still closes the request as failed, so metrics and dashboards see it.
        fail_turn(runtime, turn, "server error")
        raise
    return close_turn(runtime, turn)


@router.post(
    "/ask/stream", response_class=EventSourceResponse, dependencies=[Depends(per_ip_limit)]
)
def ask_stream(turn: Started, runtime: Runtime) -> Iterator[ServerSentEvent]:
    """Node events as the graph runs, then the validated answer. Answer tokens are not
    streamed: nothing is shown before the validator passes it."""
    if turn.cached is not None:
        yield ServerSentEvent(event="answer", data=serve_from_cache(runtime, turn, turn.cached))
        return
    try:
        for node in stream_graph(runtime, turn):
            yield ServerSentEvent(event="node", data={"node": node})
    except KeyBudgetError:
        fail_turn(runtime, turn, "key budget reached")
        yield ServerSentEvent(event="error", data=limit_detail("key_budget_reached", None))
        return
    except GatewayError:
        fail_turn(runtime, turn, "model unavailable")
        yield ServerSentEvent(event="error", data=limit_detail("model_unavailable", None))
        return
    except Exception:
        fail_turn(runtime, turn, "server error")
        raise
    yield ServerSentEvent(event="answer", data=close_turn(runtime, turn))


class ApproveBody(BaseModel):
    thread_id: UUID
    approve: bool


class ApproveResponse(BaseModel):
    thread_id: UUID
    ticket_id: UUID
    status: Literal["filed", "rejected"]


def _resume_gate(runtime: AppRuntime, thread_id: UUID, verdict: ApprovalVerdict) -> AgentState:
    config = thread_config(thread_id)
    if not runtime.graph.get_state(config).interrupts:
        raise HTTPException(409, detail="no ticket is waiting for approval on this thread")
    runtime.graph.invoke(
        Command(resume=verdict.model_dump(mode="json")), config, context=runtime.agent
    )
    return AgentState.model_validate(runtime.graph.get_state(config).values)


@router.post(
    "/approve",
    dependencies=[Depends(per_ip_limit), Depends(require_admin), Depends(require_approver)],
)
def approve(
    body: ApproveBody, role: Annotated[Role, Depends(demo_role)], runtime: Runtime
) -> ApproveResponse:
    if thread_owner(runtime.agent.engine, body.thread_id) is None:
        raise HTTPException(404, detail="thread not found")
    verdict = ApprovalVerdict(
        approve=body.approve, approver_id=demo_user_id(runtime.agent.engine, role.value)
    )
    # Two approvals at once (a double click) would both resume the same checkpoint.
    lock = f"approve:{body.thread_id}"
    if not runtime.redis.set(lock, "1", nx=True, ex=60):
        raise HTTPException(409, detail="an approval for this thread is already in progress")
    try:
        state = _resume_gate(runtime, body.thread_id, verdict)
    finally:
        runtime.redis.delete(lock)
    assert state.ticket_id is not None, "a paused thread always has a proposed ticket"
    set_request_decision(runtime.agent.engine, state.request_id, state.decision or "answered")
    tag_trace(state.request_id, body.thread_id, "admin")
    record_event("gate resumed", {"ticket_id": str(state.ticket_id), "approve": body.approve})
    return ApproveResponse(
        thread_id=body.thread_id,
        ticket_id=state.ticket_id,
        status="filed" if state.approval == "approved" else "rejected",
    )


@router.get("/threads/{thread_id}/history")
def thread_history(
    thread_id: UUID, user: Annotated[UserContext, Depends(current_user)], runtime: Runtime
) -> list[Turn]:
    if thread_owner(runtime.agent.engine, thread_id) != user.id:
        raise HTTPException(404, detail="thread not found")
    values = runtime.graph.get_state(thread_config(thread_id)).values
    return [Turn.model_validate(turn) for turn in values.get("history", [])]


@router.get("/tickets", dependencies=[Depends(require_admin)])
def tickets(runtime: Runtime) -> list[TicketOut]:
    return list_tickets(runtime.agent.engine)
