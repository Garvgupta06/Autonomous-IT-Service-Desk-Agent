# Autonomous IT Service Desk Agent

A multi-agent AI assistant for IT support. It classifies a user's message, routes it to the right agent, and asks for approval before it changes anything. Unclear requests get a clarifying question instead of a guess.

This is a college prototype. Retrieval (RAG) and the Jira client are built but not yet connected to the main flow, and all actions are simulated. See "Current status" for exactly what works today.

## How it works today

Every message goes through a LangGraph state machine:

```
User message  (POST /chat)
     |
     v
 Entry router --(action waiting for approval?)--> Approval handler
     |
     v
 Intent classifier (Gemini) -> knowledge_question | action_request | unclear
     |
     +-- knowledge_question --> RAG stub        (placeholder, real RAG not connected yet)
     +-- action_request -----> Action agent     (role check, then asks for approval)
     +-- unclear / low confidence --> Clarifying question
     |
     v
 Response returned
```

Design points that are already in the code:

- **The LLM proposes, the code enforces.** The model only picks which action was asked for. A permissions table decides whether the user's role may perform it.
- **Approval before action.** Allowed actions are proposed first and only run after the user replies "yes".
- **Audit log.** Executed, denied and cancelled actions are logged (in memory for now).
- **Per-thread state.** The graph uses a checkpointer, so a conversation keeps its state under its `thread_id`, which is how an approval reply finds the pending action.
- **Safe fallback.** Unclear or low-confidence messages (below 0.6) get a clarifying question.

## Current status

| Component | Branch | Status |
|---|---|---|
| Intent classifier (Gemini, structured output) | `feature/orchestrator` | Working |
| Routing graph and `/chat` endpoint | `feature/orchestrator` | Working |
| Action agent: role check, approval, audit log | `feature/orchestrator` | Working, actions simulated |
| Ticket role policy (`rbac.py`) and status rules (`lifecycle.py`) | `feature/orchestrator` | Written, not yet used by the agent |
| Jira Cloud client (create, read, move, comment) | `feature/orchestrator` | Written, not yet used by the agent |
| History-aware classification | not in repo yet | The classifier currently reads only the latest message |
| Document ingestion, chunking, BM25 and semantic retrieval | `feature/rag` | Written with tests, not connected to the graph |
| Hybrid fusion of BM25 and semantic results | not in repo yet | Planned |
| Web UI / Slack front-end | `feature/frontend` | Not started (README only) |

`main` currently holds an older snapshot of the orchestrator work, from before the Jira and ticket modules.

## Project structure (`feature/orchestrator`)

```
src/
  main.py                    FastAPI app: /health and /chat
  state.py                   Shared AgentState
  graph.py                   Graph wiring and routing
  orchestrator/
    classifier.py            Intent classification
    action_agent.py          Action proposal, approval, audit log
    permissions.py           Role -> allowed actions (used by the action agent)
    stubs.py                 Placeholder RAG agent and clarifying question
  tickets/
    rbac.py                  Roles, scopes and approval policy for tickets
    lifecycle.py             Allowed ticket status changes
  jira/
    client.py                Jira Cloud REST client
tests/
  test_all.py                Offline tests plus live-LLM tests
  manual/jira_check.py       Checks the Jira connection
pytest.ini                   Defines the "llm" test marker
```

RAG code lives on `feature/rag` under `backend/rag/` (`ingestion.py`, `chunking.py`, `bm25.py`, `semantic.py`, `embedder.py`) with tests in `tests/rag/`. The folder layout of the two branches still needs to be agreed before they are merged.

## Setup

Requires Python 3.10 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root (it is git-ignored):

```
GOOGLE_API_KEY=your_gemini_key

# Only needed for the Jira client
JIRA_BASE_URL=https://yoursite.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your_token
JIRA_PROJECT_KEY=DESK
```

A free Gemini key is available from Google AI Studio. Never commit `.env`.

The RAG branch uses a local Ollama server for embeddings (default model `nomic-embed-text`) and `pypdf` and `numpy`.

## Running

```bash
uvicorn src.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to try the endpoints.

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "message": "please unlock my account", "thread_id": "demo1"}'
```

Approve with a second message on the same `thread_id`:

```json
{"user_id": "u1", "message": "yes", "thread_id": "demo1"}
```

Use a new `thread_id` for each new conversation. State is held in memory, so restarting the server clears it.

## Demo users

| user_id | Role | Allowed actions |
|---|---|---|
| u1 | employee | unlock account |
| u2 | it_admin | unlock account, grant access |

## Tests

```bash
pytest -m "not llm" -v     # offline tests, no API calls
pytest -v                  # also runs the live Gemini tests
python -m tests.manual.jira_check    # needs the Jira values in .env
```

The `llm` tests call Gemini, so they need a valid key and use free-tier quota.

## Limitations

- Account unlocks and access grants are simulated. No real system is touched.
- The knowledge-question path returns a placeholder until RAG is connected.
- Approval comes from the same user who asked. A real setup would use a separate approver.
- Roles are a hard-coded table, not an identity provider.
- State and the audit log are in memory and are lost on restart.
- Jira and the ticket policy exist as modules but are not part of the chat flow yet.

## Direction

Following mentor feedback, the next phase is to make the agent work on the user's own machine: scan the laptop with read-only checks, diagnose from that evidence, propose the top two fixes for that device, and run a fix only after approval. Jira becomes the place where unresolved cases are escalated with the scan attached. This is planned and not yet implemented.

## Branches

- `main`: shared version (older snapshot for now)
- `feature/orchestrator`: backend, orchestration, Jira client, ticket policy
- `feature/rag`: knowledge base ingestion and retrieval
- `feature/frontend`: user interface