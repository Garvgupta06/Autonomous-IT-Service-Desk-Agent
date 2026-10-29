from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from src.state import AgentState

load_dotenv()
class IntentResult(BaseModel):
    intent: Literal["knowledge_question","action_request","unclear"]
    confidence: float = Field(ge=0.0, le=1.0)
    category: Literal["network", "storage", "performance", "general", "none"] = "general"

llm=ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
classifier_llm = llm.with_structured_output(IntentResult)

SYSTEM_PROMPT = """You classify IT helpdesk messages into exactly one intent:
- knowledge_question: the user needs troubleshooting help or instructions
  (e.g. "my VPN won't connect", "how do I reset my password")
- action_request: the user wants a system action performed
  (e.g. "unlock my account", "give me access to Jira")
- unclear: too vague to act on (e.g. "my email is broken")
Also pick the problem category:
- network: wifi, internet, vpn, connection problems
- storage: disk space, full drive, files
- performance: slow, lagging, freezing, high memory or cpu
- general: a device problem that fits none of the above
- none: not about a problem on the user's laptop (how-to questions, policy, accounts)
Also return a confidence between 0 and 1. Use a low value if unsure."""

def classify_intent(state: AgentState) -> dict:
    result = classifier_llm.invoke([
        ("system", SYSTEM_PROMPT),
        ("human", state["user_message"]),
    ])
    return {"detected_intent": result.intent, "confidence": result.confidence,
            "category": result.category}