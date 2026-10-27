"""Semantic retrieval: cosine similarity over chunk embeddings (NumPy only).

All chunk vectors are L2-normalised once at build time, so a search is a single
matrix-vector product. No vector database is used; this is adequate for the
small knowledge base of this project. Scores are cosine similarities in [-1, 1].
"""
from __future__ import annotations

import logging
from typing import Iterable

import numpy as np

from .embedder import Embedder, EmbeddingError
from .models import Chunk
from .retrieval_base import SearchResult

logger = logging.getLogger(__name__)


def _normalise_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0          # zero vector stays zero (similarity 0), no NaN
    return matrix / norms


class SemanticRetriever:
    """In-memory embedding index. Building it calls the embedder once for all chunks.

    Raises ``EmbeddingError`` if embedding fails. A hybrid caller can catch it
    and fall back to BM25 alone.
    """

    def __init__(self, chunks: Iterable[Chunk], embedder: Embedder, min_score: float | None = None) -> None:
        self._chunks: list[Chunk] = list(chunks)
        self._embedder = embedder
        self.min_score = min_score
        self._matrix = np.zeros((0, 0), dtype=np.float32)

        if self._chunks:
            vectors = np.asarray(embedder.embed_documents([c.text for c in self._chunks]), dtype=np.float32)
            if vectors.ndim != 2 or vectors.shape[0] != len(self._chunks):
                raise EmbeddingError(
                    f"embedder returned shape {vectors.shape} for {len(self._chunks)} chunks"
                )
            self._matrix = _normalise_rows(vectors)
        logger.info("Semantic index built: %d chunks, dim=%d", len(self._chunks), self._matrix.shape[1] if self._chunks else 0)

    def __len__(self) -> int:
        return len(self._chunks)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Return up to ``top_k`` chunks by cosine similarity, best first.

        An empty/whitespace query or an empty index returns ``[]`` without
        calling the embedder. Ties are broken by original chunk order.
        """
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        if not query.strip() or not self._chunks:
            return []

        q = np.asarray(self._embedder.embed_query(query), dtype=np.float32)
        if q.ndim != 1 or q.shape[0] != self._matrix.shape[1]:
            raise EmbeddingError(
                f"query embedding has shape {q.shape}, expected ({self._matrix.shape[1]},)"
            )
        norm = np.linalg.norm(q)
        if norm == 0:
            return []
        scores = self._matrix @ (q / norm)

        order = np.lexsort((np.arange(len(scores)), -scores))      # score desc, then chunk order
        results: list[SearchResult] = []
        for pos in order[:top_k]:
            score = float(scores[pos])
            if self.min_score is not None and score < self.min_score:
                break
            results.append(SearchResult(self._chunks[pos], score, len(results) + 1))
        return results
