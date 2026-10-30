import json
from dataclasses import asdict

from src.state import AgentState
from src.scanner.checks import run_for
from src.orchestrator.classifier import llm
from src.scanner.fixes import suggest_fixes

DIAGNOSE_PROMPT = """You are an IT support agent. The user reported a problem, and a scan of
their laptop returned the findings below.
Rules:
- Use ONLY the findings. Never invent problems or numbers.
- Say what the scan found and which findings most likely relate to the user's problem.
- If nothing looks wrong, say so plainly and suggest escalating to IT.
- Keep it under 120 words."""


def scan_node(state: AgentState) -> dict:
    findings = run_for(state.get("category") or "general")
    return {"findings": [asdict(f) for f in findings]}


def diagnose_node(state: AgentState) -> dict:
    reply = llm.invoke([
        ("system", DIAGNOSE_PROMPT),
        ("human", f"User problem: {state['user_message']}\n\n"
                  f"Findings:\n{json.dumps(state['findings'], indent=2)}"),
    ])
    text = reply.text
    pending = None
    fixes = suggest_fixes(state["findings"])
    if fixes:
        lines = ["", "Suggested fixes:"]
        for i, fix in enumerate(fixes, 1):
            lines.append(f"{i}. {fix['title']} ({fix['risk']} risk)")
        auto = next((f for f in fixes if f["automatic"]), None)
        if auto:
            lines.append(f"\nReply 'yes' to run: {auto['title']}. Reply 'no' to cancel.")
            pending = f"fix:{auto['id']}"
        text = text + "\n" + "\n".join(lines)
    return {"response": text, "pending_action": pending}