"""route -> retrieve -> (abstain | answer -> validate) -> (propose_ticket -> human_gate -> act) -> finish"""

from typing import Protocol

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from bas_assistant.agent import nodes
from bas_assistant.agent.nodes import AgentContext, Update
from bas_assistant.agent.state import AgentState, AnswerOut, Passage, TicketDraft, Turn, UserContext
from bas_assistant.observability.tracing import SpanAttributes, tracer

Graph = CompiledStateGraph[AgentState, AgentContext, AgentState, AgentState]

# The only classes a checkpoint may rebuild. Without the list LangGraph accepts any
# importable class with a warning, and says it will refuse them in a future release,
# which would strand every thread paused at the human gate.
CHECKPOINT_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[UserContext, Passage, AnswerOut, TicketDraft, Turn]
)


class Node(Protocol):
    """A node that needs the runtime; LangGraph passes it by keyword."""

    def __call__(self, state: AgentState, runtime: Runtime[AgentContext]) -> Update: ...


# What a node decided, never what it read or wrote: no question, passage or answer text.
SPAN_FIELDS = ("route", "decision", "attempts", "retrieval_ms", "rerank_ms", "approval")
COUNTED_FIELDS = ("retrieved", "validation_errors")


def _span_attributes(update: Update) -> SpanAttributes:
    attributes: SpanAttributes = {}
    for field in SPAN_FIELDS:
        value = update.get(field)
        if value is not None:
            attributes[f"agent.{field}"] = value if isinstance(value, int) else str(value)
    for field in COUNTED_FIELDS:
        value = update.get(field)
        if isinstance(value, list):
            attributes[f"agent.{field}_count"] = len(value)
    return attributes


def traced(name: str, node: Node) -> Node:
    """Run a node inside its own span. human_gate is left out: interrupt() raises to pause,
    which a span would record as an error."""

    def run(state: AgentState, runtime: Runtime[AgentContext]) -> Update:
        with tracer.start_as_current_span(f"node {name}") as span:
            update = node(state, runtime)
            span.set_attributes(_span_attributes(update))
            return update

    return run


def build_graph(checkpointer: BaseCheckpointSaver[str]) -> Graph:
    graph = StateGraph(AgentState, context_schema=AgentContext)
    graph.add_node("route", traced("route", nodes.route))
    graph.add_node("retrieve", traced("retrieve", nodes.retrieve))
    graph.add_node("abstain", nodes.abstain)
    graph.add_node("answer", traced("answer", nodes.answer))
    graph.add_node("validate", traced("validate", nodes.validate))
    graph.add_node("propose_ticket", traced("propose_ticket", nodes.propose_ticket))
    graph.add_node("human_gate", nodes.human_gate)
    graph.add_node("act", traced("act", nodes.act))
    graph.add_node("finish", nodes.finish)

    graph.add_edge(START, "route")
    graph.add_edge("route", "retrieve")
    graph.add_conditional_edges("retrieve", nodes.after_retrieve)
    graph.add_edge("abstain", "finish")
    graph.add_edge("answer", "validate")
    graph.add_conditional_edges("validate", nodes.after_validate)
    graph.add_conditional_edges("propose_ticket", nodes.after_propose)
    graph.add_conditional_edges("human_gate", nodes.after_gate)
    graph.add_edge("act", "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer)
