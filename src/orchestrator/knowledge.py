import logging
from pathlib import Path

from src.orchestrator.classifier import llm

log = logging.getLogger(__name__)

KNOWLEDGE_BASE = Path(__file__).resolve().parents[2] / "data" / "knowledge_base" / "raw"
_bm25 = None

RAG_PROMPT = """You are an IT support agent. Answer the user's question using ONLY the
runbook excerpts below. If they do not cover it, say so and suggest raising a ticket.
Give short numbered steps. Keep it under 150 words."""


def _keyword_search(query: str, top_k: int) -> list[dict]:
    """Offline fallback: BM25 keyword search over the runbooks (no Ollama needed)."""
    global _bm25
    if _bm25 is None:
        from backend.rag.ingestion import ingest_directory
        from backend.rag.chunking import chunk_documents
        from backend.rag.bm25 import BM25Retriever
        docs = ingest_directory(KNOWLEDGE_BASE).documents
        _bm25 = BM25Retriever(chunk_documents(docs))
    return [{"text": r.chunk.text, "source": r.chunk.source,
             "chunk_id": r.chunk.chunk_id, "score": float(r.score)}
            for r in _bm25.search(query, top_k=top_k)]


def get_runbook_chunks(query: str, top_k: int = 2) -> list[dict]:
    """Runbook lookup that can never break the agent."""
    try:
        from backend.rag.service import retrieve      # hybrid search (needs Ollama)
        return retrieve(query, top_k=top_k)
    except Exception as exc:
        log.warning("Hybrid RAG unavailable (%s); using keyword search", exc)
    try:
        return _keyword_search(query, top_k)
    except Exception as exc:
        log.warning("Keyword search failed too, continuing without runbooks: %s", exc)
        return []


def format_chunks(chunks: list[dict]) -> str:
    return "\n\n".join(f"[{c['source']}]\n{c['text'][:800]}" for c in chunks)


def sources_line(chunks: list[dict]) -> str:
    return "Sources: " + ", ".join(sorted({c["source"] for c in chunks}))


def rag_node(state) -> dict:
    chunks = get_runbook_chunks(state["user_message"], top_k=3)
    if not chunks:
        return {"response": "I couldn't find a runbook for that. "
                            "Please raise a ticket and IT will help."}
    reply = llm.invoke([
        ("system", RAG_PROMPT),
        ("human", f"Question: {state['user_message']}\n\n"
                  f"Runbook excerpts:\n{format_chunks(chunks)}"),
    ])
    return {"response": reply.text + "\n\n" + sources_line(chunks)}