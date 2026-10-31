from dataclasses import dataclass


class PermissionDenied(Exception):
    """The user's role does not allow this."""


class ApprovalRequired(Exception):
    """Allowed, but a human must approve first. Different from denied."""


@dataclass(frozen=True)
class User:
    id: str
    role: str
    team: str | None = None


@dataclass(frozen=True)
class Grant:
    scope: str                      # "own", "team" or "all"
    needs_approval: bool = False


USERS = {
    "u1":  User("u1",  "employee",   "alpha"),
    "u3":  User("u3",  "employee",   "alpha"),
    "u4":  User("u4",  "employee",   "beta"),
    "m1":  User("m1",  "manager",    "alpha"),
    "b1":  User("b1",  "boss"),
    "u2":  User("u2",  "it_admin"),
    "bot": User("bot", "desk_agent"),
}

POLICY = {
    "employee": {
        "ticket.create": Grant("own"),
        "ticket.view":   Grant("own"),
    },
    "manager": {
        "ticket.create": Grant("own"),
        "ticket.view":   Grant("team"),
    },
    "boss": {
        "ticket.create": Grant("own"),
        "ticket.view":   Grant("all"),
    },
    "desk_agent": {
        "ticket.create":        Grant("all"),
        "ticket.view":          Grant("all"),
        "ticket.change_status": Grant("all", needs_approval=True),
    },
    "it_admin": {
        "ticket.create":        Grant("all"),
        "ticket.view":          Grant("all"),
        "ticket.change_status": Grant("all"),
        "ticket.assign":        Grant("all"),
    },
}


def _in_scope(user: User, grant: Grant, ticket: dict) -> bool:
    if grant.scope == "all":
        return True
    if grant.scope == "own":
        return ticket["reporter"] == user.id
    if grant.scope == "team":
        reporter = USERS.get(ticket["reporter"])
        return (reporter is not None
                and user.team is not None
                and reporter.team == user.team)
    return False


def authorize(user_id: str, action: str, ticket: dict | None = None,
              approved: bool = False) -> User:
    user = USERS.get(user_id)
    if user is None:
        raise PermissionDenied(f"unknown user '{user_id}'")

    grant = POLICY.get(user.role, {}).get(action)
    if grant is None:
        raise PermissionDenied(f"role '{user.role}' cannot {action}")

    if ticket is not None and not _in_scope(user, grant, ticket):
        raise PermissionDenied(f"{user.id} cannot {action} on that ticket")

    if grant.needs_approval and not approved:
        raise ApprovalRequired(f"{action} by {user.role} needs approval")

    return user


def visible(user_id: str, tickets: list[dict]) -> list[dict]:
    """Return only the tickets this user is allowed to see."""
    user = USERS.get(user_id)
    grant = POLICY.get(user.role, {}).get("ticket.view") if user else None
    if grant is None:
        raise PermissionDenied(f"'{user_id}' cannot view tickets")
    return [t for t in tickets if _in_scope(user, grant, t)]