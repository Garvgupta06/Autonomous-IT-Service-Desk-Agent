"""Reusable retrieval service for other components (e.g. the orchestration agent).

    from backend.rag.service import retrieve
    hits = retrieve("VPN error 691", top_k=3)
    # -> [{"text": ..., "source": ..., "chunk_id": ..., "score": ...}, ...]

* Returns retrieved chunks only (no LLM answer generation).
* The retriever (ingestion -> chunking -> embeddings -> HybridRetriever) is built
  on the first call and reused afterwards. A failed build is NOT cached, so the
  next call retries (e.g. after Ollama has been started).
* Importing this module has no side effects: it does not touch Ollama or the
  filesystem and never starts the interactive CLI (run_pipeline.py is not imported).
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from .chunking import chunk_documents
from .embedder import EmbeddingError, OllamaEmbedder
from .hybrid import HybridRetriever
from .ingestion import ingest_directory
from .retrieval_base import Retriever

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE = ROOT / "data" / "knowledge_base" / "raw"   # same location as run_pipeline.py
EMBEDDING_MODEL = "nomic-embed-text"

_retriever: Retriever | None = None
_lock = threading.Lock()


class RetrievalUnavailableError(RuntimeError):
    """The retriever cannot be built or used (no documents, Ollama down, model missing)."""


def _build_retriever() -> Retriever:
    result = ingest_directory(KNOWLEDGE_BASE)          # NotADirectoryError if the folder is missing
    for failure in result.failures:
        logger.warning("Knowledge-base file skipped: %s (%s)", failure.path, failure.reason)
    chunks = chunk_documents(result.documents)
    if not chunks:
        raise RetrievalUnavailableError(f"no documents could be ingested from {KNOWLEDGE_BASE}")
    logger.info("Building retriever from %d document(s), %d chunk(s)", len(result.documents), len(chunks))
    return HybridRetriever(chunks, OllamaEmbedder(model=EMBEDDING_MODEL))


def get_retriever() -> Retriever:
    """Return the shared retriever, building it on first use (thread-safe)."""
    global _retriever
    if _retriever is None:
        with _lock:
            if _retriever is None:
                try:
                    _retriever = _build_retriever()
                except EmbeddingError as exc:
                    raise RetrievalUnavailableError(
                        f"embedding service unavailable (is Ollama running with '{EMBEDDING_MODEL}' pulled?): {exc}"
                    ) from exc
                except NotADirectoryError as exc:
                    raise RetrievalUnavailableError(str(exc)) from exc
    return _retriever


def warm_up() -> None:
    """Optional: build the retriever eagerly (e.g. at application start-up)."""
    get_retriever()


def reset_retriever() -> None:
    """Forget the shared retriever so the next call rebuilds it (e.g. after the KB changes)."""
    global _retriever
    with _lock:
        _retriever = None


def retrieve(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Return the top ``top_k`` knowledge-base chunks for ``query``, best first.

    Each dict has ``text``, ``source`` (filename), ``chunk_id`` and ``score``
    (hybrid fusion score; only meaningful for ordering). An empty or
    whitespace-only query returns ``[]``.

    Raises:
        ValueError: ``top_k`` is not positive.
        RetrievalUnavailableError: the retriever cannot be built or used.
    """
    if top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    if not query or not query.strip():
        return []
    try:
        results = get_retriever().search(query, top_k=top_k)
    except EmbeddingError as exc:
        raise RetrievalUnavailableError(f"embedding service failed during search: {exc}") from exc
    return [
        {"text": r.chunk.text, "source": r.chunk.source, "chunk_id": r.chunk.chunk_id, "score": float(r.score)}
        for r in results
    ]
