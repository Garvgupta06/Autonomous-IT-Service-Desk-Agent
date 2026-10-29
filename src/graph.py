from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.state import AgentState
from src.orchestrator.classifier import classify_intent
from src.orchestrator.stubs import rag_stub, clarify_node
from src.orchestrator.action_agent import propose_action, handle_approval
from src.orchestrator.diagnosis import scan_node, diagnose_node

CONFIDENCE_THRESHOLD = 0.6


def entry_router(state: AgentState) -> str:
    return "approval" if state.get("pending_action") else "classify"


def route_by_intent(state: AgentState) -> str:
    if state["detected_intent"] == "unclear":
        return "clarify"
    if (state["confidence"] or 0) < CONFIDENCE_THRESHOLD:
        return "clarify"
    if state["detected_intent"] == "action_request":
        return "action"
    if state.get("category") == "none":
        return "rag"          # general question, no scan needed
    return "scan"             # a problem on this laptop


builder = StateGraph(AgentState)

builder.add_node("classify", classify_intent)
builder.add_node("scan", scan_node)
builder.add_node("diagnose", diagnose_node)
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
    {"scan": "scan", "rag": "rag", "action": "action", "clarify": "clarify"},
)
builder.add_edge("scan", "diagnose")

for node in ("diagnose", "rag", "action", "approval", "clarify"):
    builder.add_edge(node, END)

graph = builder.compile(checkpointer=MemorySaver())