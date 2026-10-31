"""Hybrid retrieval combining BM25 keyword search and semantic search."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from .embedder import Embedder
from .models import Chunk
from .retrieval import BM25Retriever
from .retrieval_base import SearchResult
from .semantic import SemanticRetriever


class HybridRetriever:
    """Combine keyword and semantic rankings using Reciprocal Rank Fusion."""

    def __init__(
        self,
        chunks: Sequence[Chunk],
        embedder: Embedder,
        *,
        rrf_k: int = 60,
        semantic_min_score: float | None = None,
    ) -> None:
        if rrf_k <= 0:
            raise ValueError("rrf_k must be positive")

        self.chunks = list(chunks)
        self.rrf_k = rrf_k
        self.bm25 = BM25Retriever(self.chunks)
        self.semantic = SemanticRetriever(
            self.chunks,
            embedder,
            min_score=semantic_min_score,
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Return results ranked using both retrieval methods."""

        if top_k <= 0:
            raise ValueError("top_k must be positive")

        if not query.strip() or not self.chunks:
            return []

        # Retrieve a wider candidate set before combining rankings.
        candidate_k = min(len(self.chunks), max(top_k * 3, 10))

        keyword_results = self.bm25.search(
            query,
            top_k=candidate_k,
        )
        semantic_results = self.semantic.search(
            query,
            top_k=candidate_k,
        )

        fused_scores: dict[str, float] = defaultdict(float)
        chunks_by_id: dict[str, Chunk] = {}

        for results in (keyword_results, semantic_results):
            for rank, result in enumerate(results, start=1):
                chunk_id = result.chunk.chunk_id
                chunks_by_id[chunk_id] = result.chunk
                fused_scores[chunk_id] += 1.0 / (
                    self.rrf_k + rank
                )

        ordered_ids = sorted(
            fused_scores,
            key=lambda chunk_id: (
                -fused_scores[chunk_id],
                chunk_id,
            ),
        )

        return [
            SearchResult(
                chunk=chunks_by_id[chunk_id],
                score=fused_scores[chunk_id],
                rank=rank,
            )
            for rank, chunk_id in enumerate(
                ordered_ids[:top_k],
                start=1,
            )
        ]