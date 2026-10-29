import pytest
from src.tickets.rbac import authorize, visible, PermissionDenied, ApprovalRequired

T1 = {"key": "DESK-1", "reporter": "u1"}   # team alpha
T2 = {"key": "DESK-2", "reporter": "u3"}   # team alpha
T3 = {"key": "DESK-3", "reporter": "u4"}   # team beta
ALL = [T1, T2, T3]


def keys(tickets):
    return [t["key"] for t in tickets]


def test_employee_sees_only_own():
    assert keys(visible("u1", ALL)) == ["DESK-1"]


def test_manager_sees_own_team_only():
    assert keys(visible("m1", ALL)) == ["DESK-1", "DESK-2"]


@pytest.mark.parametrize("user", ["b1", "bot", "u2"])
def test_boss_agent_admin_see_everything(user):
    assert len(visible(user, ALL)) == 3


def test_employee_cannot_open_someone_elses_ticket():
    with pytest.raises(PermissionDenied):
        authorize("u1", "ticket.view", T2)


@pytest.mark.parametrize("user", ["u1", "m1", "b1"])
def test_read_only_roles_cannot_change_status(user):
    with pytest.raises(PermissionDenied):
        authorize(user, "ticket.change_status", T1)


def test_desk_agent_needs_approval_to_change_status():
    with pytest.raises(ApprovalRequired):
        authorize("bot", "ticket.change_status", T1)
    assert authorize("bot", "ticket.change_status", T1, approved=True).id == "bot"


def test_admin_changes_status_without_approval():
    assert authorize("u2", "ticket.change_status", T1).id == "u2"


def test_only_admin_can_assign():
    assert authorize("u2", "ticket.assign", T1)
    with pytest.raises(PermissionDenied):
        authorize("bot", "ticket.assign", T1)


def test_employee_cannot_create_for_someone_else():
    with pytest.raises(PermissionDenied):
        authorize("u1", "ticket.create", {"reporter": "u3"})


def test_desk_agent_can_create_for_others():
    assert authorize("bot", "ticket.create", {"reporter": "u3"})


def test_unknown_user_denied():
    with pytest.raises(PermissionDenied):
        authorize("ghost", "ticket.view", T1)