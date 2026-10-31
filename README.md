# Autonomous IT Service Desk Agent (ResolveIQ)

A local, laptop-aware IT support agent. A user reports a problem in chat. The agent runs targeted read-only scans on the laptop, diagnoses from the evidence, suggests fixes, runs an allowlisted fix only after approval, then re-scans to show before and after. Tickets are created in Jira Cloud.

This is a college prototype. The sections "Current status" and "Limitations" say exactly what works today and what does not.

## How it works

Every message goes through a LangGraph state machine:

```
User message  (POST /chat)
     |
     v
 Entry router --(fix or action waiting for approval?)--> Approval handler
     |
     v
 Intent classifier (Gemini) -> intent + problem category
     |
     +-- problem on this laptop --> Scan (read-only, category only) --> Diagnose --> Suggested fixes
     +-- general question -------> RAG stub (real RAG not connected yet)
     +-- action request ---------> Action agent (role check, then approval)
     +-- unclear / low confidence -> Clarifying question
```

Example flow:

1. User: "my laptop is very slow"
2. The agent scans CPU, memory, disks and top processes. Rules flag findings; the LLM only explains them.
3. It suggests up to two fixes, for example "Delete temporary files older than 1 day" and "Close <app> (using X GB)".
4. User: "yes". The allowlisted fix runs.
5. The agent re-scans and shows before and after.

Design principles in the code:

- **The LLM proposes, the code enforces.** Rules flag problems, an allowlist decides which fixes can run.
- **Approval before any change.** Fixes and actions run only after the user replies "yes".
- **Dry run by default.** The temp-file cleaner counts what it would delete unless told otherwise.
- **Verify after fixing.** Each fix is mapped to the scan that proves it worked.
- **Audit log.** Executed, denied, cancelled and failed actions are logged (in memory for now).
- **Per-thread state.** A checkpointer keeps a conversation under its `thread_id`, so an approval reply finds the pending fix.

## Current status

| Component | Status |
|---|---|
| Intent classifier and routing graph (Gemini) | Working |
| Targeted scans: system, CPU, memory, disks, network, top processes | Working |
| Diagnosis with suggested fixes (top 2) | Working |
| Allowlisted fixes: clean temp files, flush DNS | Working, real actions, dry run supported |
| Approval, then fix, then re-scan with before/after comparison | Working |
| Account unlock and access grant with role check | Working, simulated actions |
| `POST /chat` and `POST /tickets` (creates a real Jira issue, label `desk-agent`) | Working |
| Jira Cloud client (create, read, move, comment) | Working, only ticket creation is used by the API |
| Web UI (chat and ticket form wired to the backend) | Working. Login, dashboard and ticket list use sample data |
| RAG: ingestion, chunking, BM25, semantic search, hybrid fusion, `retrieve()` | Built and tested separately (`backend/rag/`). Not yet connected to the agent |
| Jira ticket worker (agent picks up tickets itself) | Planned |
| Action registry and risk tiers | Planned |
| Authentication | Planned |

## Project structure

```
src/
  main.py                    FastAPI app: /health, /chat, /tickets
  state.py                   Shared AgentState
  graph.py                   Graph wiring and routing
  orchestrator/
    classifier.py            Intent and category classification
    diagnosis.py             Scan node and diagnose node (suggests fixes)
    action_agent.py          Action proposal, approval, fix execution, audit log
    permissions.py           Role -> allowed actions
    stubs.py                 Placeholder RAG node and clarifying question
  scanner/
    checks.py                Read-only checks and category routing
    fixes.py                 Fix allowlist, fix suggestions, before/after comparison
  tickets/
    rbac.py, lifecycle.py    Ticket role policy and status rules (not yet used)
  jira/
    client.py                Jira Cloud REST client
backend/rag/                 Retrieval service (ingestion, chunking, BM25, semantic, hybrid)
data/knowledge_base/raw/     Runbooks used for retrieval
index.html, css/, js/        Web UI
tests/
  test_scanner.py            Scanner and fix tests (offline)
  test_all.py, test_rbac.py  Orchestrator and policy tests
  rag/                       RAG tests
  manual/                    Manual end-to-end scripts (step_b.py, jira_check.py)
```

## Setup

Requires Python 3.10 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
pip install numpy pypdf         # needed by the RAG package
```

Create a `.env` file in the project root (it is git-ignored):

```
GOOGLE_API_KEY=your_gemini_key

# Needed for ticket creation
JIRA_BASE_URL=https://yoursite.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your_token
JIRA_PROJECT_KEY=DESK
```

Never commit `.env`. The RAG package uses a local Ollama server for embeddings (model `nomic-embed-text`).

## Running

Backend (keep it on localhost, there is no authentication yet):

```bash
uvicorn src.main:app --host 127.0.0.1 --port 8000
```

UI, from the repository root, in a second window:

```bash
python -m http.server 5500
```

Open `http://localhost:5500`, go to AI Chat and type "my laptop is very slow", then "yes".

You can also call the API directly. Open `http://127.0.0.1:8000/docs`, or run the end-to-end script:

```bash
python -m tests.manual.step_b
```

## Demo users

| user_id | Role | Allowed actions |
|---|---|---|
| u1 | employee | unlock account |
| u2 | it_admin | unlock account, grant access |

## Tests

```bash
pytest tests/test_scanner.py -v     # scanner and fix tests, offline
pytest -m "not llm" -v              # all offline tests
pytest -v                           # also runs live Gemini tests (needs a key)
python -m tests.manual.jira_check   # needs the Jira values in .env
```

Scanner tests use fixed sample findings on purpose, so results do not depend on the machine. The RAG connection test needs Ollama running.

## Limitations

- **No authentication yet.** `/chat` trusts the `user_id` in the request, so anyone who can reach the API can claim any role. Run it on `127.0.0.1` only.
- Thread IDs are not tied to a user, and approval does not re-check permissions at execution time.
- The audit log and conversation state are in memory and are lost on restart.
- Roles are a hard-coded table, not an identity provider.
- Account unlocks and access grants are simulated. Only the two allowlisted fixes (clean temp files, flush DNS) act on the machine.
- The general-question path returns a placeholder until RAG is connected.
- The UI login, dashboard and ticket list use sample data. Only chat and ticket creation reach the backend.
- A "Close this app" suggestion is advice only. The agent never closes applications.

## Roadmap

1. Connect RAG: retrieve runbook chunks, combine them with scan findings and cite the runbook source.
2. Action registry: one place defining each action's risk tier, allowed roles, admin need, executor and verification check, with a re-check at execution time.
3. Real device actions: restart Wi-Fi, allowlisted service restart, enable a disabled device (admin rights needed).
4. Jira ticket worker: pick up tickets labelled `desk-agent`, run the agent, reply with a comment and update the status.
5. Security hardening: OIDC authentication, thread ownership, approval bound to the requester, durable audit log, mocked-LLM tests and rate limits.
6. Gemini-generated runbooks for a wider knowledge base.

## Branches

- `main`: current shared version
- `feature/orchestrator`: backend, scanner, fixes, Jira client
- `feature/rag`: knowledge base ingestion and retrieval
- `feature/frontend`: user interface
