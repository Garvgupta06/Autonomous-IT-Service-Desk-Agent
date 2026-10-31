"""Text embedding via a local Ollama server (default model: nomic-embed-text).

Uses only the standard library for HTTP (urllib), so no extra HTTP dependency is
needed. The ``Embedder`` protocol lets tests (or a different provider later)
replace Ollama without touching the retriever.

Prerequisite on the machine running the code:  ``ollama pull nomic-embed-text``
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Embeddings could not be obtained (server down, model missing, bad reply)."""


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """Return a float32 array of shape (len(texts), dim)."""
        ...

    def embed_query(self, text: str) -> np.ndarray:
        """Return a float32 vector of shape (dim,)."""
        ...


class OllamaEmbedder:
    """Calls Ollama's ``POST /api/embed`` endpoint.

    nomic-embed-text is trained with task prefixes; they are applied by default
    ("search_document: " for chunks, "search_query: " for queries) and can be
    set to "" for models that do not use them.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        timeout: float = 60.0,
        batch_size: int = 32,
        document_prefix: str = "search_document: ",
        query_prefix: str = "search_query: ",
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.batch_size = batch_size
        self.document_prefix = document_prefix
        self.query_prefix = query_prefix

    def _post_embed(self, inputs: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model, "input": inputs}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/embed", data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            hint = f" - is the model installed? run: ollama pull {self.model}" if exc.code == 404 else ""
            raise EmbeddingError(f"Ollama returned HTTP {exc.code}{hint}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise EmbeddingError(f"cannot reach Ollama at {self.base_url}: {exc}") from exc
        except ValueError as exc:  # includes JSONDecodeError
            raise EmbeddingError(f"Ollama returned invalid JSON: {exc}") from exc

        embeddings = body.get("embeddings") if isinstance(body, dict) else None
        if not isinstance(embeddings, list) or len(embeddings) != len(inputs):
            raise EmbeddingError("unexpected Ollama response: 'embeddings' missing or wrong length")
        return embeddings

    def _embed(self, texts: list[str], prefix: str) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        rows: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = [prefix + t for t in texts[i : i + self.batch_size]]
            rows.extend(self._post_embed(batch))
        try:
            matrix = np.asarray(rows, dtype=np.float32)
        except (ValueError, TypeError) as exc:
            raise EmbeddingError(f"embeddings are not numeric/rectangular: {exc}") from exc
        if matrix.ndim != 2 or matrix.shape[1] == 0:
            raise EmbeddingError("embeddings have an invalid shape")
        return matrix

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts, self.document_prefix)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([text], self.query_prefix)[0]
