    
"""BM25-based retrieval for the IT Service Desk Agent."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from backend.rag.models import Chunk


@dataclass(frozen=True)
class RetrievalResult:
    """A retrieved chunk with its relevance score."""

    chunk: Chunk
    score: float


def tokenize(text: str) -> list[str]:
    """Convert text into lowercase word tokens."""
    return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())


class BM25Retriever:
    """Retrieve relevant document chunks using the BM25 ranking algorithm."""

    def __init__(
        self,
        chunks: Sequence[Chunk],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be greater than zero.")
        if not 0 <= b <= 1:
            raise ValueError("b must be between zero and one.")

        self.chunks = list(chunks)
        self.k1 = k1
        self.b = b

        self._tokens = [tokenize(chunk.text) for chunk in self.chunks]
        self._lengths = [len(tokens) for tokens in self._tokens]
        self._avg_length = (
            sum(self._lengths) / len(self._lengths)
            if self._lengths
            else 0.0
        )

        self._document_frequency: dict[str, int] = {}

        for tokens in self._tokens:
            for term in set(tokens):
                self._document_frequency[term] = (
                    self._document_frequency.get(term, 0) + 1
                )

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Return the highest-scoring chunks for a query."""
        if top_k < 1:
            raise ValueError("top_k must be at least one.")

        query_terms = set(tokenize(query))

        if not query_terms or not self.chunks:
            return []

        document_count = len(self.chunks)
        results: list[RetrievalResult] = []

        for index, chunk in enumerate(self.chunks):
            document_tokens = self._tokens[index]
            document_length = self._lengths[index]

            if document_length == 0:
                continue

            term_counts: dict[str, int] = {}
            for term in document_tokens:
                term_counts[term] = term_counts.get(term, 0) + 1

            score = 0.0

            for term in query_terms:
                frequency = term_counts.get(term, 0)

                if frequency == 0:
                    continue

                df = self._document_frequency.get(term, 0)

                # BM25 inverse document frequency.
                idf = (
                    __import__("math").log(
                        1 + (document_count - df + 0.5) / (df + 0.5)
                    )
                )

                length_normalization = (
                    1 - self.b
                    + self.b * document_length / self._avg_length
                ) if self._avg_length else 1.0

                denominator = frequency + self.k1 * length_normalization

                score += idf * (
                    frequency * (self.k1 + 1) / denominator
                )

            if score > 0:
                results.append(RetrievalResult(chunk=chunk, score=score))

        results.sort(key=lambda result: result.score, reverse=True)
        return results[:top_k]

