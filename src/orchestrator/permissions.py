USER_ROLES = {
    "u1": "employee",
    "u2": "it_admin",
}

ROLE_PERMISSIONS = {
    "employee": {"unlock_account"},
    "it_admin": {"unlock_account", "grant_access"},
}