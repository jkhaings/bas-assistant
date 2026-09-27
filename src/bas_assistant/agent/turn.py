"""One question through the API: limits, cache, graph run, request row, response."""

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from bas_assistant.agent.prompts import PROMPT_VERSION
from bas_assistant.agent.records import (
    RequestOutcome,
    close_request,
    create_thread,
    open_request,
    record_request_chunks,
    thread_owner,
)
from bas_assistant.agent.state import AgentState, Decision, Turn, UserContext, turn_input
from bas_assistant.audit import write_audit
from bas_assistant.cost.budget import next_reset, refund_allowance, spent_today, take_allowance
from bas_assistant.cost.cache import cache_key, get_cached, put_cached
from bas_assistant.cost.usage import record_cache_hit
from bas_assistant.guardrails.input import redact
from bas_assistant.guardrails.limits import limit_error
from bas_assistant.llm.router import Route
from bas_assistant.runtime import AppRuntime

logger = logging.getLogger(__name__)

SNIPPET_CHARS = 300


class Citation(BaseModel):
    chunk_id: str
    document_title: str
    page: int
    source_url: str
    snippet: str


class TurnResult(BaseModel):
    """The cacheable part of an answer."""

    answer: str
    citations: list[Citation]
    decision: Decision
    route: Route | None
    model: str | None


class AskResponse(TurnResult):
    request_id: UUID
    thread_id: UUID
    approval_required: bool
    ticket_id: UUID | None
    notes: list[str]
    cache_hit: bool


@dataclass(frozen=True)
class OpenTurn:
    request_id: UUID
    thread_id: UUID
    user: UserContext
    question: str
    new_thread: bool
    cached: TurnResult | None
    # The allowance day to refund is the day it was taken, even if the request ends later.
    opened_at: datetime
    started: float


def thread_config(thread_id: UUID) -> RunnableConfig:
    return {"configurable": {"thread_id": str(thread_id)}}


def _check_daily_cap(runtime: AppRuntime, user: UserContext, now: datetime) -> None:
    if spent_today(runtime.agent.engine, now) < runtime.daily_usd_cap:
        return
    write_audit(
        runtime.agent.engine,
        None,
        actor=user.role,
        action="daily_cap_reached",
        detail={"cap_usd": str(runtime.daily_usd_cap)},
    )
    raise limit_error(503, "daily_budget_reached", next_reset(now))


# Every visitor of a role shares its demo user, so this is a per-role quota; the per-IP
# limiter (guardrails/limits.py) is the per-visitor control.
def _take_allowance(runtime: AppRuntime, user: UserContext, now: datetime) -> None:
    if take_allowance(runtime.redis, user.id, runtime.user_daily_questions, now):
        return
    write_audit(
        runtime.agent.engine,
        None,
        actor=user.role,
        action="allowance_used",
        detail={"limit": runtime.user_daily_questions},
    )
    raise limit_error(429, "daily_allowance_used", next_reset(now))


def _check_thread(runtime: AppRuntime, thread_id: UUID, user: UserContext) -> None:
    # Another role's thread is reported as missing: its history may hold passages this
    # role is not allowed to see.
    if thread_owner(runtime.agent.engine, thread_id) != user.id:
        raise HTTPException(404, detail="thread not found")
    if runtime.graph.get_state(thread_config(thread_id)).interrupts:
        raise HTTPException(409, detail="thread is waiting for ticket approval")


def _key(runtime: AppRuntime, question: str, user: UserContext) -> str:
    return cache_key(question, user.role, runtime.corpus_version, PROMPT_VERSION)


def _audit_decision(
    runtime: AppRuntime, turn: OpenTurn, decision: Decision, route: Route | None
) -> None:
    write_audit(
        runtime.agent.engine,
        turn.request_id,
        actor=turn.user.role,
        action="decision",
        detail={"decision": decision, "route": route, "prompt_version": PROMPT_VERSION},
    )


def open_turn(
    runtime: AppRuntime, question: str, thread_id: UUID | None, user: UserContext
) -> OpenTurn:
    """Refuse early (404/409/503/429) or record the request and return the open turn."""
    now = datetime.now(UTC)
    if thread_id is not None:
        _check_thread(runtime, thread_id, user)
    _check_daily_cap(runtime, user, now)
    # Nothing past this line sees the raw question: not the cache, the requests row, the
    # checkpoints, the history or any model.
    redaction = redact(question)
    question = redaction.text
    # Follow-ups depend on earlier turns, so only a thread's first question is cacheable.
    cached = None
    if thread_id is None:
        cached = get_cached(runtime.redis, _key(runtime, question, user), TurnResult)
    # A cache hit costs nothing, so it does not count against the allowance.
    if cached is None:
        _take_allowance(runtime, user, now)
    new_thread = thread_id is None
    thread_id = thread_id or create_thread(runtime.agent.engine, user.id)
    request_id = uuid4()
    open_request(runtime.agent.engine, request_id, thread_id, user, question)
    if redaction.counts:
        write_audit(
            runtime.agent.engine,
            request_id,
            actor=user.role,
            action="input_redacted",
            detail={"entities": redaction.counts},
        )
    return OpenTurn(
        request_id, thread_id, user, question, new_thread, cached, now, time.perf_counter()
    )


def _elapsed_ms(turn: OpenTurn) -> int:
    return round((time.perf_counter() - turn.started) * 1000)


def _respond(result: TurnResult, turn: OpenTurn, state: AgentState | None) -> AskResponse:
    return AskResponse.model_validate(
        result.model_dump()
        | {
            "request_id": turn.request_id,
            "thread_id": turn.thread_id,
            "approval_required": result.decision == "paused",
            "ticket_id": state.ticket_id if state else None,
            "notes": state.notes if state else [],
            "cache_hit": state is None,
        }
    )


def serve_from_cache(runtime: AppRuntime, turn: OpenTurn, cached: TurnResult) -> AskResponse:
    engine = runtime.agent.engine
    record_cache_hit(engine, turn.request_id, cached.route or "fast")
    close_request(
        engine,
        turn.request_id,
        RequestOutcome(cached.route, cached.decision, _elapsed_ms(turn), 0, 0),
    )
    runtime.graph.update_state(
        thread_config(turn.thread_id),
        {"history": [Turn(question=turn.question, answer=cached.answer)]},
        as_node="finish",
    )
    _audit_decision(runtime, turn, cached.decision, cached.route)
    return _respond(cached, turn, None)


def invoke_graph(runtime: AppRuntime, turn: OpenTurn) -> None:
    runtime.graph.invoke(
        turn_input(turn.request_id, turn.question, turn.user),
        thread_config(turn.thread_id),
        context=runtime.agent,
    )


def stream_graph(runtime: AppRuntime, turn: OpenTurn) -> Iterator[str]:
    """Yield each node name as it finishes."""
    for update in runtime.graph.stream(
        turn_input(turn.request_id, turn.question, turn.user),
        thread_config(turn.thread_id),
        context=runtime.agent,
        stream_mode="updates",
    ):
        yield from (name for name in update if name != "__interrupt__")


def _citations(state: AgentState) -> list[Citation]:
    if state.draft is None or not state.draft.answerable:
        return []
    by_id = {passage.chunk_id: passage for passage in state.retrieved}
    cited = [by_id[chunk_id] for chunk_id in state.draft.citations]
    return [
        Citation(
            chunk_id=p.chunk_id,
            document_title=p.document_title,
            page=p.page,
            source_url=p.source_url,
            snippet=p.text[:SNIPPET_CHARS],
        )
        for p in cited
    ]


def close_turn(runtime: AppRuntime, turn: OpenTurn) -> AskResponse:
    snapshot = runtime.graph.get_state(thread_config(turn.thread_id))
    state = AgentState.model_validate(snapshot.values)
    decision: Decision = "paused" if snapshot.interrupts else state.decision or "failed"
    close_request(
        runtime.agent.engine,
        turn.request_id,
        RequestOutcome(
            state.route, decision, _elapsed_ms(turn), state.retrieval_ms, state.rerank_ms
        ),
    )
    cited = state.draft.citations if state.draft else []
    record_request_chunks(runtime.agent.engine, turn.request_id, state.retrieved, cited)
    # A rejected answer still cost model calls, so it keeps its place in the allowance.
    _audit_decision(runtime, turn, decision, state.route)
    logger.info("request %s decision=%s route=%s", turn.request_id, decision, state.route)
    result = TurnResult(
        answer=state.final_answer,
        citations=_citations(state),
        decision=decision,
        route=state.route,
        model=state.answer_model,
    )
    cacheable = decision in ("answered", "abstained") and not state.notes and not state.ticket_id
    if turn.new_thread and cacheable:
        put_cached(runtime.redis, _key(runtime, turn.question, turn.user), result)
    return _respond(result, turn, state)


def fail_turn(runtime: AppRuntime, turn: OpenTurn) -> None:
    """Every model deployment failed: record it and give the user their question back."""
    close_request(
        runtime.agent.engine,
        turn.request_id,
        RequestOutcome(None, "failed", _elapsed_ms(turn), 0, 0),
    )
    refund_allowance(runtime.redis, turn.user.id, turn.opened_at)
    _audit_decision(runtime, turn, "failed", None)
    logger.warning("request %s failed: model unavailable", turn.request_id)
