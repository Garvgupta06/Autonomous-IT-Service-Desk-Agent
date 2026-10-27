import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
AUTH = (os.getenv("JIRA_EMAIL", ""), os.getenv("JIRA_API_TOKEN", ""))
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


class JiraError(Exception):
    pass


def _request(method: str, path: str, **kwargs) -> dict:
    resp = requests.request(
        method, f"{BASE_URL}{path}",
        auth=AUTH, headers=HEADERS, timeout=15, **kwargs,
    )
    if not resp.ok:
        raise JiraError(f"Jira returned {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.text else {}


def whoami() -> dict:
    return _request("GET", "/rest/api/3/myself")


def list_projects() -> list[dict]:
    return _request("GET", "/rest/api/3/project/search").get("values", [])

PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "")


def _adf(text: str) -> dict:
    """Wrap plain text in the JSON format Jira Cloud requires."""
    paragraphs = [
        {"type": "paragraph", "content": [{"type": "text", "text": line}]}
        for line in text.split("\n") if line.strip()
    ] or [{"type": "paragraph", "content": []}]
    return {"type": "doc", "version": 1, "content": paragraphs}


def list_issue_types(project_key: str = PROJECT_KEY) -> list[str]:
    data = _request("GET", f"/rest/api/3/project/{project_key}")
    return [t["name"] for t in data.get("issueTypes", [])]


def create_issue(summary: str, description: str, requester: str,
                 labels: list[str] | None = None,
                 issue_type: str = "Task") -> dict:
    body = f"Requested by: {requester}\n{description}"
    payload = {
        "fields": {
            "project": {"key": PROJECT_KEY},
            "issuetype": {"name": issue_type},
            "summary": summary,
            "description": _adf(body),
            "labels": [f"requester-{requester}"] + (labels or []),
        }
    }
    return _request("POST", "/rest/api/3/issue", json=payload)


def get_issue(key: str) -> dict:
    data = _request("GET", f"/rest/api/3/issue/{key}")
    f = data["fields"]
    return {
        "key": data["key"],
        "summary": f["summary"],
        "status": f["status"]["name"],
        "labels": f.get("labels", []),
    }