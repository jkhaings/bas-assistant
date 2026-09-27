"""route -> retrieve -> (abstain | answer -> validate) -> (propose_ticket -> human_gate -> act) -> finish"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from bas_assistant.agent import nodes
from bas_assistant.agent.nodes import AgentContext
from bas_assistant.agent.state import AgentState, AnswerOut, Passage, TicketDraft, Turn, UserContext

Graph = CompiledStateGraph[AgentState, AgentContext, AgentState, AgentState]

# The only classes a checkpoint may rebuild. Without the list LangGraph accepts any
# importable class with a warning, and says it will refuse them in a future release,
# which would strand every thread paused at the human gate.
CHECKPOINT_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[UserContext, Passage, AnswerOut, TicketDraft, Turn]
)


def build_graph(checkpointer: BaseCheckpointSaver[str]) -> Graph:
    graph = StateGraph(AgentState, context_schema=AgentContext)
    graph.add_node("route", nodes.route)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("abstain", nodes.abstain)
    graph.add_node("answer", nodes.answer)
    graph.add_node("validate", nodes.validate)
    graph.add_node("propose_ticket", nodes.propose_ticket)
    graph.add_node("human_gate", nodes.human_gate)
    graph.add_node("act", nodes.act)
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
