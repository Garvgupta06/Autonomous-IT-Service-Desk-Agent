from fastapi import FastAPI
from src.graph import graph
from pydantic import BaseModel


app = FastAPI(title="desk-agent")

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