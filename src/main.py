from fastapi import FastAPI

app = FastAPI(title="desk-agent")
@app.get("/health")
def health():
    return {"status":"ok"}