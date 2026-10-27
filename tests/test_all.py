import pytest

from src.tickets import db as dbmod
from src.tickets.db import init_db
from src.tickets.repository import (
    create_ticket, get_ticket, list_tickets, change_status,
)
from src.tickets.lifecycle import InvalidTransition, ALLOWED_TRANSITIONS, STATUSES
from src.orchestrator import action_agent
from src.orchestrator.action_agent import ActionChoice, AUDIT_LOG
from src.orchestrator.permissions import ROLE_PERMISSIONS


# ---------- setup helpers ----------

@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the ticket code at a throwaway database for one test."""
    monkeypatch.setattr(dbmod, "db_path", tmp_path / "test.db")
    init_db()


class FakeActionLLM:
    """Stands in for Gemini so the RBAC tests are fast and repeatable."""
    def __init__(self, action):
        self.action = action

    def invoke(self, messages):
        return ActionChoice(action=self.action)


# ---------- tickets (offline) ----------

def test_create_and_fetch_ticket(fresh_db):
    t = create_ticket("VPN down", reporter="u1", category="vpn", priority="high")
    assert t["key"].startswith("DESK-")
    assert t["status"] == "open"
    assert get_ticket(t["key"])["title"] == "VPN down"


def test_list_filters_by_reporter(fresh_db):
    create_ticket("a", reporter="u1")
    create_ticket("b", reporter="u2")
    assert len(list_tickets(reporter="u1")) == 1


def test_invalid_priority_rejected(fresh_db):
    with pytest.raises(ValueError):
        create_ticket("x", reporter="u1", priority="urgent!!")


# ---------- lifecycle (offline) ----------

def test_full_lifecycle_then_closed_is_final(fresh_db):
    key = create_ticket("flow", reporter="u1")["key"]
    for status in ["in_progress", "waiting_on_user", "in_progress", "resolved", "closed"]:
        assert change_status(key, status)["status"] == status
    with pytest.raises(InvalidTransition):
        change_status(key, "open")


def test_cannot_skip_resolved(fresh_db):
    key = create_ticket("skip", reporter="u1")["key"]
    change_status(key, "in_progress")
    with pytest.raises(InvalidTransition):
        change_status(key, "closed")


def test_unknown_status_rejected(fresh_db):
    key = create_ticket("bad", reporter="u1")["key"]
    with pytest.raises(InvalidTransition):
        change_status(key, "banana")


def test_rules_only_use_real_statuses():
    for source, targets in ALLOWED_TRANSITIONS.items():
        assert source in STATUSES
        assert targets <= set(STATUSES)


# ---------- RBAC and approval (offline) ----------

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


# ---------- live LLM (needs API key, uses quota) ----------

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