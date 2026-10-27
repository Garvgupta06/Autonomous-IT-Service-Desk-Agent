from src.jira.client import list_issue_types, create_issue, get_issue

print("Issue types in this project:", list_issue_types())

created = create_issue(
    summary="VPN keeps disconnecting",
    description="User reports the VPN drops every few minutes.",
    requester="u1",
    labels=["vpn"],
)
print("Created:", created["key"])
print("Fetched:", get_issue(created["key"]))