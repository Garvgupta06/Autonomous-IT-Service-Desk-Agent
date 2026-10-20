from datetime import datetime
from typing import Literal
from pydantic import BaseModel
from src.state import AgentState
from src.orchestrator.classifier import llm
from src.orchestrator.permissions import USER_ROLES, ROLE_PERMISSIONS

class ActionChoice(BaseModel):
    action: Literal["unlock_account", "grant_access", "unknown"]

action_llm = llm.with_structured_output(ActionChoice)

AUDIT_LOG = []

def log(user_id, action, outcome):
    AUDIT_LOG.append({"time": datetime.now().isoformat(), "user": user_id,
                      "action": action, "outcome": outcome})
    print("AUDIT:", AUDIT_LOG[-1])

# mocked executors: stand-ins for real AD / SaaS API calls
EXECUTORS = {
    "unlock_account": lambda uid: f"Account unlocked for {uid}. (simulated)",
    "grant_access":   lambda uid: f"Access granted to {uid}. (simulated)",
}

def propose_action(state: AgentState) -> dict:
    choice = action_llm.invoke([
        ("system", "Pick the IT action the user is requesting: "
                   "unlock_account, grant_access, or unknown."),
        ("human", state["user_message"]),
    ])
    action = choice.action
    uid = state["user_id"]

    if action == "unknown":
        return {"response": "I can unlock accounts or grant access. Which one do you need?",
                "pending_action": None}

    role = USER_ROLES.get(uid, "guest")
    if action not in ROLE_PERMISSIONS.get(role, set()):
        log(uid, action, "DENIED")
        return {"response": f"Your role ({role}) isn't permitted to {action}. "
                            "I've escalated this to IT staff.",
                "pending_action": None}

    return {"response": f"I can {action} for you. Reply 'yes' to approve or 'no' to cancel.",
            "pending_action": action}

def handle_approval(state: AgentState) -> dict:
    uid, action = state["user_id"], state["pending_action"]
    if state["user_message"].strip().lower() in ("yes", "y", "approve"):
        result = EXECUTORS[action](uid)
        log(uid, action, "EXECUTED")
        return {"response": result, "pending_action": None}
    log(uid, action, "CANCELLED")
    return {"response": "Cancelled. No changes were made.", "pending_action": None}