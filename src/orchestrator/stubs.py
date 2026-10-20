from src.state import AgentState

def rag_stub(state: AgentState) -> dict:
    return {"response": "[RAG STUB] Here are the steps from the runbook..."}

def action_stub(state: AgentState) -> dict:
    return {"response": "[ACTION STUB] I'll need approval before doing that."}

def clarify_node(state: AgentState) -> dict:
    return {"response": "Could you tell me a bit more? For example, what exactly "
                        "is happening, and what were you trying to do?"}