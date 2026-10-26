# Autonomous IT Service Desk Agent

An AI-powered IT support system designed to answer common IT questions using knowledge retrieval and assist with ticket management.

## Project Modules

- RAG and Knowledge Retrieval
- Orchestration Agent
- Frontend Interface

## Team Workflow

Each team member will work on a separate Git branch.
Changes will be reviewed before merging into the main branch.

## orchestrator workflow
A multi-agent AI assistant that handles routine IT support requests (troubleshooting questions, account unlocks, access grants) and escalates to humans when it is not confident or not permitted to act.

This is a working prototype built to demonstrate the full architecture at small scale. Enterprise systems (Active Directory, ServiceNow) are mocked.

## How it works

Every message goes through a LangGraph state machine:

```
User message
     |
     v
 Entry router --(action pending approval?)--> Approval handler
     |
     v
 Intent classifier (LLM) -> knowledge_question | action_request | unclear
     |
     +-- knowledge_question --> RAG agent        (retrieves from runbooks)
     +-- action_request -----> Action agent      (RBAC check + approval)
     +-- unclear / low confidence --> Clarifying question
     |
     v
 Conversation history updated -> response returned
```

Key design points:

- **The LLM proposes, the code enforces.** The model only identifies which action was requested. A fixed permissions table decides whether the user's role may perform it.
- **Human-in-the-loop approval.** Sensitive actions are proposed first and only executed after the user replies "yes".
- **Audit logging.** Every executed, denied or cancelled action is logged.
- **Multi-turn memory.** Conversation state is stored per `thread_id`, so follow-up messages are understood in context.
- **Safe fallback.** Vague or low-confidence messages get a clarifying question instead of a guess.

## Current status

| Component | Status |
|---|---|
| Intent classifier (Gemini, structured output) | Done |
| Routing graph (LangGraph) | Done |
| Action agent with RBAC and approval | Done (actions are simulated) |
| Multi-turn conversation history | Done |
| FastAPI `/chat` endpoint | Done |
| RAG agent (hybrid dense + BM25 retrieval) | In progress (`feature/rag`), stub in place |
| Slack bot front-end | In progress (`feature/frontend`) |
| ITSM (ServiceNow/Jira) integration | Planned, will be mocked |

## Project structure

```
src/
  main.py                  FastAPI app (/health, /chat)
  state.py                 Shared AgentState
  graph.py                 LangGraph wiring and routing
  orchestrator/
    classifier.py          Intent classification node
    action_agent.py        Action proposal, RBAC check, approval, audit log
    permissions.py         Role -> allowed actions table
    stubs.py               Placeholder RAG agent and clarifying-question node
tests/                     Scripts to exercise each part
data/                      Runbooks for the knowledge base
```

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```

Create a `.env` file in the project root (it is git-ignored):

```
GOOGLE_API_KEY=your_key_here
```

A free key is available from Google AI Studio.

## Running

Start the API from the project root:

```bash
uvicorn src.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to try the endpoints in the browser.

Example request:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "message": "please unlock my account", "thread_id": "demo1"}'
```

Reply to the approval prompt using the same `thread_id`:

```json
{"user_id": "u1", "message": "yes", "thread_id": "demo1"}
```

Use a new `thread_id` for each new conversation. Conversation memory is held in RAM, so restarting the server clears it.

## Demo users

| user_id | Role | Allowed actions |
|---|---|---|
| u1 | employee | unlock account |
| u2 | it_admin | unlock account, grant access |

## Tests

Run from the project root:

```bash
python -m tests.classifier_test
python -m tests.test_graph
python -m tests.action_test
```

These call the live LLM, so they need a valid `GOOGLE_API_KEY`.

## Scope and limitations

- Active Directory and SaaS actions are simulated; no real systems are touched.
- Approval is currently given by the requesting user. In production, sensitive actions would require approval from a separate IT approver.
- Roles come from a hard-coded table, not a real identity provider.
- Conversation memory is in-process and not persistent.

## Team branches

- `main`: shared, working version
- `feature/orchestrator`: backend and orchestration
- `feature/rag`: knowledge base and retrieval
- `feature/frontend`: Slack bot and UI