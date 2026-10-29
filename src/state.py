from typing import TypedDict, List, Optional


class AgentState(TypedDict):
    user_id: str
    user_message: str
    conversation_history: List[dict]
    detected_intent: Optional[str]
    confidence: Optional[float]
    response: Optional[str]
    pending_action: Optional[str]