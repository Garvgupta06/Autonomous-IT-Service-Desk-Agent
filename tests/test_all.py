import pytest

from src.tickets.lifecycle import InvalidTransition, ALLOWED_TRANSITIONS, STATUSES, check_transition
from src.orchestrator import action_agent
from src.orchestrator.action_agent import ActionChoice, AUDIT_LOG
from src.orchestrator.permissions import ROLE_PERMISSIONS


# ---------- helpers ----------

class FakeActionLLM:
    """Stands in for Gemini so the action agent tests are fast and repeatable."""

    def __init__(self, action):
        self.action = action

    def invoke(self, messages):
        return ActionChoice(action=self.action)


# ---------- lifecycle rules (offline) ----------

def test_allowed_move_passes():
    check_transition("open", "in_progress")        # raises nothing


def test_closed_is_final():
    with pytest.raises(InvalidTransition):
        check_transition("closed", "open")


def test_cannot_skip_resolved():
    with pytest.raises(InvalidTransition):
        check_transition("in_progress", "closed")


def test_unknown_status_rejected():
    with pytest.raises(InvalidTransition):
        check_transition("open", "banana")


def test_rules_only_use_real_statuses():
    for source, targets in ALLOWED_TRANSITIONS.items():
        assert source in STATUSES
        assert targets <= set(STATUSES)


# ---------- action agent: roles, approval, audit log (offline) ----------

def test_employee_cannot_grant_access_but_admin_can():
    assert "grant_access" not in ROLE_PERMISSIONS["employee"]
    assert "grant_access" in ROLE_PERMISSIONS["it_admin"]


def test_denied_action_is_logged(monkeypatch):
    monkeypatch.setattr(action_agent, "action_llm", FakeActionLLM("grant_access"))
    out = action_agent.propose_action({"user_id": "u1", "user_message": "give me Jira"})
    assert out["pending_action"] is None
    assert AUDIT_LOG[-1]["outcome"] == "DENIED"


def test_allowed_action_waits_for_approval(monkeypatch):
    monkeypatch.setattr(action_agent, "action_llm", FakeActionLLM("grant_access"))
    out = action_agent.propose_action({"user_id": "u2", "user_message": "give me Jira"})
    assert out["pending_action"] == "grant_access"


def test_approval_yes_executes():
    state = {"user_id": "u1", "user_message": "yes", "pending_action": "unlock_account"}
    out = action_agent.handle_approval(state)
    assert out["pending_action"] is None
    assert AUDIT_LOG[-1]["outcome"] == "EXECUTED"


def test_approval_no_cancels():
    state = {"user_id": "u1", "user_message": "no", "pending_action": "unlock_account"}
    action_agent.handle_approval(state)
    assert AUDIT_LOG[-1]["outcome"] == "CANCELLED"


# ---------- live LLM (needs GOOGLE_API_KEY, uses free-tier quota) ----------

@pytest.mark.llm
@pytest.mark.parametrize("message,expected", [
    ("my VPN keeps disconnecting", "knowledge_question"),
    ("please unlock my account", "action_request"),
    ("my email is broken", "unclear"),
    ("can you grant me access to Slack", "action_request"),
])
def test_classifier_labels(message, expected):
    from src.orchestrator.classifier import classify_intent
    assert classify_intent({"user_message": message})["detected_intent"] == expected


@pytest.mark.llm
def test_unlock_flow_end_to_end():
    from src.graph import graph
    cfg = {"configurable": {"thread_id": "pytest-unlock"}}

    def send(msg):
        return graph.invoke(
            {"user_id": "u1", "user_message": msg,
             "conversation_history": [{"role": "user", "content": msg}]},
            cfg,
        )

    assert send("please unlock my account")["pending_action"] == "unlock_account"
    assert "unlocked" in send("yes")["response"].lower()