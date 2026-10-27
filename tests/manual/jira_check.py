from src.jira.client import whoami, list_projects

me = whoami()
print("Connected as:", me["displayName"])

for p in list_projects():
    print("Project:", p["key"], "-", p["name"])