Autonomous IT Service Desk Agent (ResolveIQ)

A local, laptop-aware IT support agent. A user reports a problem in chat. The agent runs targeted read-only scans on the laptop, diagnoses from the evidence, suggests fixes grounded in IT runbooks, runs an allowlisted fix only after approval, then re-scans to show before and after. If the problem is not resolved, a ticket can be created in Jira Cloud.

In one line: an IT helpdesk that checks before it advises, asks before it acts, and verifies after it fixes.

This is a college prototype. The sections "Current status" and "Limitations" say exactly what works today and what does not.

Team
Member	Area
Garv	Backend, LangGraph orchestration, FastAPI, Jira integration
Priya	RAG: ingestion, retrieval and the knowledge base (backend/rag/)
Aanya	Frontend (static HTML, CSS and JavaScript UI)
How it works

Every message goes through a LangGraph state machine:

User message  (POST /chat)
     |
     v
 Entry router --(fix or action waiting for approval?)--> Approval handler
     |
     v
 Intent classifier (Gemini) -> intent + confidence + problem category
     |
     +-- problem on this laptop ---> Scan (read-only, category only) --> Diagnose --> Suggested fixes
     +-- general question ---------> RAG (runbook answer with cited sources)
     +-- action request -----------> Action agent (role check, then approval)
     +-- unclear / low confidence -> Clarifying question

Example flow:

User: "my laptop is very slow"
The agent scans CPU, memory, disks and top processes. Rules flag findings; the LLM only explains them.
It suggests up to two fixes grounded in runbook chunks, for example "Delete temporary files older than 1 day" and "Close <app> (using X GB)". Runbook sources are listed under the answer.
User: "yes". The allowlisted fix runs.
The agent re-scans and shows before and after.

Design principles in the code:

The LLM proposes, the code enforces. Rules flag problems, and an allowlist decides which fixes can run. The LLM cannot run commands.
Approval before any change. Fixes and actions run only after the user replies "yes". Any other reply cancels.
Dry run by default. The temp-file cleaner counts what it would delete unless told otherwise.
Verify after fixing. Each fix is mapped to the scan that proves it worked.
Audit log. Executed, denied, cancelled and failed actions are logged (in memory for now).
Per-thread state. A checkpointer keeps a conversation under its thread_id, so an approval reply finds the pending fix.
Current status
Component	Status
Intent classifier and routing graph (Gemini)	Working
Targeted scans: system, CPU, memory, disks, network, top processes	Working
Diagnosis with suggested fixes (top 2), grounded in runbooks	Working
Allowlisted fixes: clean temp files, flush DNS	Working, real actions, dry run supported
Approval, then fix, then re-scan with before/after comparison	Working
Account unlock and access grant with role check	Working, simulated actions
RAG: hybrid retrieval (BM25 + Ollama embeddings), connected to the agent, keyword fallback if Ollama is down	Working. Runbook answers cite their sources. Three runbooks so far
POST /chat and POST /tickets (creates a real Jira issue, label desk-agent)	Working
Jira Cloud client (create, read, move, comment)	Working. Only ticket creation is used by the API
Web UI	Chat and ticket form are wired to the backend. Login, dashboard and ticket list use sample data
Offline test suite	86 passed, 5 deselected
Jira ticket worker (agent picks up tickets itself)	Planned
Action registry and risk tiers	Planned
Authentication	Planned
Project structure
src/
  main.py                    FastAPI app: /health, /chat, /tickets
  state.py                   Shared AgentState
  graph.py                   Graph wiring and routing
  orchestrator/
    classifier.py            Intent and category classification
    diagnosis.py             Scan node and diagnose node (suggests fixes)
    knowledge.py             Runbook retrieval, sources line, RAG node
    action_agent.py          Action proposal, approval, fix execution, audit log
    permissions.py           Role -> allowed actions
    stubs.py                 Clarifying question node
  scanner/
    checks.py                Read-only checks and category routing
    fixes.py                 Fix allowlist, fix suggestions, before/after comparison
  tickets/
    rbac.py, lifecycle.py    Ticket role policy and status rules (written and tested, not yet used)
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
Setup

Requires Python 3.10 or newer.

bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
pip install numpy pypdf         # needed by the RAG package

Create a .env file in the project root (it is git-ignored):

GOOGLE_API_KEY=your_gemini_key

# Needed for ticket creation
JIRA_BASE_URL=https://yoursite.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your_token
JIRA_PROJECT_KEY=DESK

Never commit .env, API keys or the Jira token.

The RAG package uses a local Ollama server for embeddings:

bash
ollama pull nomic-embed-text

Ollama is optional. If it is not running, the agent falls back to keyword (BM25) search over the runbooks. After a long idle period Ollama is cold and the first request can time out; send one small embedding request to warm it up.

The UI talks to the backend at the address in js/config.js. Keep API_BASE set to http://127.0.0.1:8000 (not localhost, which can resolve to IPv6).

Running

Backend (keep it on localhost, there is no authentication yet). Restart it after every backend code change:

bash
uvicorn src.main:app --host 127.0.0.1 --port 8000

Wait for the "RAG ready" message in the log. UI, from the repository root, in a second window:

bash
python -m http.server 5500

Open http://localhost:5500, go to AI Chat and type "my laptop is very slow", then "yes". If the UI looks stale after a change, hard-refresh with Ctrl+Shift+R.

Approval is done by typing "yes" or "no" in the chat. There are no Approve and Cancel buttons yet.

You can also call the API directly. Open http://127.0.0.1:8000/docs, or run the end-to-end script:

bash
python -m tests.manual.step_b

Note: a fix is only offered when the real numbers justify it (for example the system drive at 85% or more, or DNS failing). Thresholds are not lowered to make a demo work.

Demo users
user_id	Role	Allowed actions
u1	employee	unlock account
u2	it_admin	unlock account, grant access
Tests
bash
pytest tests/test_scanner.py -v     # scanner and fix tests, offline
pytest -m "not llm" -v              # all offline tests
pytest -v                           # also runs live Gemini tests (needs a key)
python -m tests.manual.jira_check   # needs the Jira values in .env

Last run: 86 passed, 5 deselected (pytest -m "not llm" -q). Scanner tests use fixed sample findings on purpose, so results do not depend on the machine. Some RAG tests need Ollama running and can time out if Ollama is cold.

Limitations
No authentication yet. /chat trusts the user_id in the request, so anyone who can reach the API can claim any role. Run it on 127.0.0.1 only. CORS is limited to localhost.
Thread IDs are not tied to a user, and approval does not re-check permissions at execution time.
The audit log and conversation state are in memory and are lost on restart.
Roles are a hard-coded table, not an identity provider.
Account unlocks and access grants are simulated. Only the two allowlisted fixes (clean temp files, flush DNS) act on the machine.
A "Close this app" suggestion is advice only. The agent never closes applications.
Direct requests such as "flush my DNS" are not supported. Fixes are offered after a scan, and they run without a role check.
The knowledge base has only three runbooks, and retrieval has no relevance cutoff, so an unrelated runbook can be cited.
The network check detects outages, not slowness (no latency or link-speed check yet).
If Gemini fails, the API returns a raw error instead of a friendly message.
The UI login, dashboard and ticket list use sample data. Only chat and ticket creation reach the backend.
Roadmap
Finish RAG: end-to-end verification, concise grounded answers with sources, error handling, a relevance cutoff and a wider knowledge base (Gemini-generated runbooks).
Action registry: one place defining each action's risk tier, allowed roles, admin need, executor and verification check, with a re-check at execution time. This also enables direct requests like "flush my DNS".
Real device actions: restart Wi-Fi, allowlisted service restart, enable a disabled device (admin rights needed).
Jira ticket worker: pick up tickets labelled desk-agent, run the agent, reply with a comment (including the before/after result) and update the status.
Security hardening: OIDC authentication, thread ownership, approval bound to the requester, durable audit log, mocked-LLM tests, rate limits and prompt-injection testing.
UI: Approve and Cancel buttons, and real data for login, dashboard and ticket list.
Branches
main: current shared version (all feature branches are merged)
feature/orchestrator, feature/rag, feature/frontend: original feature branches, now merged