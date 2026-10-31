from fastapi import FastAPI
from src.graph import graph
from pydantic import BaseModel
from fastapi import HTTPException
from src.jira.client import create_issue, JiraError

from fastapi.middleware.cors import CORSMiddleware



app = FastAPI(title="desk-agent")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    user_id:str
    message: str
    thread_id:str="default"

class ChatResponse(BaseModel):
    response:str
    intent: str | None = None

@app.get("/health")
def health():
    return {"status":"ok"}

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    out=graph.invoke({"user_id":req.user_id, "user_message":req.message}, {"configurable":{"thread_id":req.thread_id}})
    return ChatResponse(response=out["response"], intent=out.get("detected_intent"))

class TicketRequest(BaseModel):
    title: str
    description: str
    category: str | None = None
    priority: str | None = None
    requester: str = "u1"


@app.post("/tickets")
def create_ticket(t: TicketRequest):
    labels = ["desk-agent"]
    if t.category:
        labels.append(t.category.replace(" ", "_"))     # Jira labels cannot contain spaces
    body = f"Category: {t.category}\nPriority: {t.priority}\n{t.description}"
    try:
        issue = create_issue(t.title, body, t.requester.replace(" ", "_"), labels)
    except JiraError:
        raise HTTPException(status_code=502, detail="Could not create the ticket in Jira.")
    return {"key": issue["key"]}