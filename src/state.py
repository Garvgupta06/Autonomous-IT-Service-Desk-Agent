from typing import TypedDict, List, Optional

class AgentState(TypedDict):
    user_id : str       #role of user
    user_message: str   #latest message
    converstation_history: List[dict]  
    detected_intent: Optional[str] #type of request
    confidence: Optional[float] #confidence level between 0.0 - 1.0
    response: Optional[str]     #final response