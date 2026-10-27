from src.jira.client import list_issue_types, create_issue, get_issue
from src.jira.client import whoami, list_projects
from src.jira.client import get_transitions, move_issue, add_comment, get_issue, JiraError

me = whoami()
print("Connected as:", me["displayName"])

for p in list_projects():
    print("Project:", p["key"], "-", p["name"])



print("Issue types in this project:", list_issue_types())

created = create_issue(
    summary="windows update troubleshoot",
    description="windows is crashing due to latest update.",
    requester="u1",
    labels=["windows_update"],
)
print("Created:", created["key"])
print("Fetched:", get_issue(created["key"]))


KEY = "DESK-1"      # use a ticket you created earlier

print("Now:", get_issue(KEY)["status"])
print("Available moves:", [t["to"] for t in get_transitions(KEY)])

print("Moved:", move_issue(KEY, "In Progress")["status"])
add_comment(KEY, "Bot: asked the user to restart the VPN client.")
print("Moved:", move_issue(KEY, "Done")["status"])

try:
    move_issue(KEY, "Banana")
except JiraError as e:
    print("Blocked:", e)