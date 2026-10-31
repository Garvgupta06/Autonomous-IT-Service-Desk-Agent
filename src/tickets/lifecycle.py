STATUSES  = ["open","in_progress","waiting_on_user","resolved","closed"]

ALLOWED_TRANSITIONS = {
    "open" :  {"in_progress","waiting_on_user","resolved","closed"},
    "in_progress" : {"waiting_on_user","resolved","open"},
    "waiting_on_user" : {"in_progress","resolved","closed"},
    "resolved": {"closed","open"},
    "closed":set(),
}

class InvalidTransition(Exception):
    pass

def check_transition(current: str, new:str) -> None:
    if new not in STATUSES:
        raise InvalidTransition(f"'{new}' is not a valid status")
    if new not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"cannot move from '{current}' to '{new}' ")