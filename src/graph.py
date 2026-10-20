from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.state import AgentState
from src.orchestrator.classifier import classify_intent
from src.orchestrator.stubs import rag_stub, clarify_node
from src.orchestrator.action_agent import propose_action, handle_approval

CONFIDENCE_THRESHOLD = 0.6


def entry_router(state: AgentState) -> str:
    # If an action is waiting for approval, this message is the answer to it
    return "approval" if state.get("pending_action") else "classify"


def route_by_intent(state: AgentState) -> str:
    if state["detected_intent"] == "unclear":
        return "clarify"
    if (state["confidence"] or 0) < CONFIDENCE_THRESHOLD:
        return "clarify"
    if state["detected_intent"] == "action_request":
        return "action"
    return "rag"


builder = StateGraph(AgentState)

builder.add_node("classify", classify_intent)
builder.add_node("rag", rag_stub)
builder.add_node("action", propose_action)
builder.add_node("approval", handle_approval)
builder.add_node("clarify", clarify_node)

builder.add_conditional_edges(
    START, entry_router,
    {"approval": "approval", "classify": "classify"},
)
builder.add_conditional_edges(
    "classify", route_by_intent,
    {"rag": "rag", "action": "action", "clarify": "clarify"},
)

for node in ("rag", "action", "approval", "clarify"):
    builder.add_edge(node, END)

graph = builder.compile(checkpointer=MemorySaver())