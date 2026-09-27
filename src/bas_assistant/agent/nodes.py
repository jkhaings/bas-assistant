"""Graph nodes. The model makes two decisions (route, answer); every other node is code."""

from dataclasses import dataclass
from typing import Literal

import httpx
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import ValidationError
from sqlalchemy import Engine

from bas_assistant.agent.prompts import build_messages
from bas_assistant.agent.records import TicketStatus, insert_ticket, set_ticket_status
from bas_assistant.agent.state import (
    AgentState,
    AnswerOut,
    ApprovalVerdict,
    Retriever,
    Turn,
)
from bas_assistant.api.roles import Role, acl_groups_for_role
from bas_assistant.audit import write_audit
from bas_assistant.cost.usage import record_usage
from bas_assistant.guardrails.input import injection_pattern
from bas_assistant.guardrails.output import find_violations
from bas_assistant.llm.gateway import complete
from bas_assistant.llm.router import RefusalKind, classify

ANSWER_MAX_TOKENS = 700
MAX_ANSWER_ATTEMPTS = 2
FAILED_MESSAGE = (
    "I couldn't produce an answer I can back with the documentation. "
    "Please rephrase the question or ask a colleague."
)
NO_TICKET_NOTE = "A ticket was suggested, but this role cannot create tickets."
TICKET_WITHOUT_DOCS_MESSAGE = (
    "The documentation does not cover this, so I drafted a ticket for an admin to review."
)
REFUSAL_MESSAGES: dict[RefusalKind, str] = {
    "injection": (
        "I can't follow instructions that change how I work. "
        "Ask me a question about the product documentation instead."
    ),
    "off_topic": "I only answer questions about the products in the documentation.",
}
# The model's reason is audited, not shown; a cap keeps a runaway reason out of the row.
REFUSAL_REASON_CHARS = 200

Update = dict[str, object]


@dataclass(frozen=True)
class AgentContext:
    llm: httpx.Client
    engine: Engine
    retrieve: Retriever


def screen(state: AgentState) -> Update:
    """The pattern half of the injection rail: code only, so an obvious attempt costs $0."""
    matched = injection_pattern(state.question)
    if matched is None:
        return {}
    return {"refusal": "injection", "refusal_rail": "pattern", "refusal_reason": matched}


def after_screen(state: AgentState) -> Literal["refuse", "route"]:
    return "refuse" if state.refusal else "route"


def route(state: AgentState, runtime: Runtime[AgentContext]) -> Update:
    triage = classify(runtime.context.llm, state.question)
    record_usage(runtime.context.engine, state.request_id, "router", triage.usage)
    update: Update = {"route": triage.route, "topic": triage.topic}
    if triage.refusal is not None:
        update |= {
            "refusal": triage.refusal,
            "refusal_rail": "model",
            "refusal_reason": triage.reason[:REFUSAL_REASON_CHARS],
        }
    return update


def after_route(state: AgentState) -> Literal["refuse", "retrieve"]:
    return "refuse" if state.refusal else "retrieve"


def refuse(state: AgentState, runtime: Runtime[AgentContext]) -> Update:
    assert state.refusal is not None, "refuse is only reached with a refusal"
    write_audit(
        runtime.context.engine,
        state.request_id,
        actor="input_rail",
        action="input_refused",
        detail={
            "rail": state.refusal_rail,
            "kind": state.refusal,
            "reason": state.refusal_reason,
        },
    )
    return {"decision": "refused", "final_answer": REFUSAL_MESSAGES[state.refusal]}


def retrieve(state: AgentState, runtime: Runtime[AgentContext]) -> Update:
    # The SQL filter is always the role's own groups, whatever else the state carries.
    acl_groups = acl_groups_for_role(Role(state.user.role))
    if acl_groups != state.user.acl_groups:
        raise PermissionError(f"user context for {state.user.role} does not match its ACL groups")
    result = runtime.context.retrieve(state.question, acl_groups)
    if result.embed is not None:
        record_usage(runtime.context.engine, state.request_id, "embed", result.embed)
    return {
        "retrieved": result.passages,
        "retrieval_ms": result.retrieval_ms,
        "rerank_ms": result.rerank_ms,
    }


def after_retrieve(state: AgentState) -> Literal["answer", "abstain"]:
    return "answer" if state.retrieved else "abstain"


def abstain_message(topic: str) -> str:
    searched = f" I searched for: {topic}." if topic else ""
    return (
        f"I couldn't find this in the documentation.{searched} "
        "Try naming the product model, or ask about a spec, protocol or wiring detail."
    )


def abstain(state: AgentState) -> Update:
    return {"decision": "abstained", "final_answer": abstain_message(state.topic)}


def answer(state: AgentState, runtime: Runtime[AgentContext]) -> Update:
    # If every strong deployment fails, the proxy itself falls back to fast (config).
    completion = complete(
        runtime.context.llm,
        state.route or "strong",
        build_messages(state),
        AnswerOut,
        ANSWER_MAX_TOKENS,
    )
    record_usage(runtime.context.engine, state.request_id, "answer", completion.usage)
    return {
        "draft_raw": completion.content,
        "answer_model": completion.usage.model,
        "attempts": state.attempts + 1,
    }


def validate(state: AgentState, runtime: Runtime[AgentContext]) -> Update:
    try:
        draft = AnswerOut.model_validate_json(state.draft_raw)
    except ValidationError as exc:
        return _reject(
            state, runtime, [f"the answer is not valid JSON ({exc.error_count()} errors)"]
        )
    files_ticket = draft.needs_ticket and "create_ticket" in state.user.tools_allowed
    if not draft.answerable and not files_ticket:
        # The model's own wording is never shown when it says the documents don't cover it.
        return {
            "decision": "abstained",
            "final_answer": abstain_message(state.topic),
            "validation_errors": [],
        }
    violations = find_violations(draft, state.retrieved)
    if violations:
        return _reject(state, runtime, violations)
    shown = draft.answer if draft.answerable else TICKET_WITHOUT_DOCS_MESSAGE
    return {"draft": draft, "validation_errors": [], "final_answer": shown}


def _reject(state: AgentState, runtime: Runtime[AgentContext], violations: list[str]) -> Update:
    if state.attempts < MAX_ANSWER_ATTEMPTS:
        return {"validation_errors": violations}
    write_audit(
        runtime.context.engine,
        state.request_id,
        actor="validator",
        action="answer_rejected",
        detail={"violations": violations, "attempts": state.attempts},
    )
    return {"validation_errors": violations, "decision": "failed", "final_answer": FAILED_MESSAGE}


def after_validate(state: AgentState) -> Literal["answer", "propose_ticket", "finish"]:
    if state.decision in ("failed", "abstained"):
        return "finish"
    if state.validation_errors:
        return "answer"
    if state.draft is not None and state.draft.needs_ticket:
        return "propose_ticket"
    return "finish"


def propose_ticket(state: AgentState, runtime: Runtime[AgentContext]) -> Update:
    draft = state.draft.ticket_draft if state.draft else None
    if draft is None or "create_ticket" not in state.user.tools_allowed:
        return {"notes": [NO_TICKET_NOTE]}
    ticket_id = insert_ticket(runtime.context.engine, state.request_id, draft)
    write_audit(
        runtime.context.engine,
        state.request_id,
        actor=state.user.role,
        action="ticket_proposed",
        detail={"ticket_id": str(ticket_id)},
    )
    return {"ticket_id": ticket_id, "approval": "pending", "decision": "paused"}


def after_propose(state: AgentState) -> Literal["human_gate", "finish"]:
    return "human_gate" if state.ticket_id else "finish"


def human_gate(state: AgentState, runtime: Runtime[AgentContext]) -> Update:
    # interrupt() pauses here and the checkpoint is saved; POST /approve resumes the node,
    # which re-runs from the top, so nothing before this line may have side effects.
    verdict = ApprovalVerdict.model_validate(interrupt({"ticket_id": str(state.ticket_id)}))
    assert state.ticket_id is not None, "human_gate is only reached with a proposed ticket"
    status: TicketStatus = "approved" if verdict.approve else "rejected"
    set_ticket_status(runtime.context.engine, state.ticket_id, status, verdict.approver_id)
    write_audit(
        runtime.context.engine,
        state.request_id,
        actor=str(verdict.approver_id),
        action=f"ticket_{status}",
        detail={"ticket_id": str(state.ticket_id)},
    )
    return {"approval": status, "approver_id": verdict.approver_id}


def after_gate(state: AgentState) -> Literal["act", "finish"]:
    return "act" if state.approval == "approved" else "finish"


def act(state: AgentState, runtime: Runtime[AgentContext]) -> Update:
    """File the approved ticket in the internal table (Jira is the production path)."""
    assert state.ticket_id is not None, "act is only reached with an approved ticket"
    assert state.approver_id is not None, "act is only reached after an approval"
    set_ticket_status(runtime.context.engine, state.ticket_id, "filed", state.approver_id)
    write_audit(
        runtime.context.engine,
        state.request_id,
        actor="agent",
        action="ticket_filed",
        detail={"ticket_id": str(state.ticket_id)},
    )
    return {}


def finish(state: AgentState) -> Update:
    decision = state.decision
    if decision in (None, "paused"):
        # A ticket filed for something the documents don't cover is still an abstain.
        answered = state.draft is not None and state.draft.answerable
        decision = "answered" if answered else "abstained"
    return {
        "decision": decision,
        "history": [Turn(question=state.question, answer=state.final_answer)],
    }
