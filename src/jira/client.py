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