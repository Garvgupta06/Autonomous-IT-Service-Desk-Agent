"""Keyword retrieval with Okapi BM25 (pure Python, no extra dependencies).

The index is built in memory from ``Chunk`` objects produced by the chunking
stage. Scoring per query term t for chunk d:

    idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5))
    score  = sum_t idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |d| / avgdl))

BM25 is strong for exact tokens such as error codes ("0x80070005") and product
names, which is why it is kept alongside semantic retrieval later.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import Chunk
from .retrieval_base import SearchResult

logger = logging.getLogger(__name__)

# Alphanumeric runs; "0x80070005" stays whole, "wi-fi" -> "wi", "fi".
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

# Deliberately small: IDF already down-weights common words; this only removes noise.
STOPWORDS: frozenset[str] = frozenset(
    "a an and are as at be but by for from has have how i if in is it its my of on or "
    "so that the their then there this to was we what when where which who why will with you your".split()
)


def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    """Lower-case alphanumeric tokens; no stemming (keeps error codes intact)."""
    tokens = _TOKEN_RE.findall(text.lower())
    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens


@dataclass(frozen=True)
class BM25Config:
    k1: float = 1.5
    b: float = 0.75
    remove_stopwords: bool = True

    def __post_init__(self) -> None:
        if self.k1 < 0:
            raise ValueError("k1 must not be negative")
        if not 0.0 <= self.b <= 1.0:
            raise ValueError("b must be between 0 and 1")


class BM25Retriever:
    """In-memory BM25 index over chunks. Rebuild by creating a new instance."""

    def __init__(self, chunks: Iterable[Chunk], config: BM25Config | None = None) -> None:
        self.config = config or BM25Config()
        self._chunks: list[Chunk] = list(chunks)
        self._lengths: list[int] = []
        self._postings: dict[str, list[tuple[int, int]]] = defaultdict(list)  # term -> [(chunk_pos, tf)]

        for pos, chunk in enumerate(self._chunks):
            tokens = tokenize(chunk.text, self.config.remove_stopwords)
            self._lengths.append(len(tokens))
            for term, tf in Counter(tokens).items():
                self._postings[term].append((pos, tf))

        total = sum(self._lengths)
        self._avgdl: float = total / len(self._chunks) if self._chunks else 0.0
        logger.info("BM25 index built: %d chunks, %d terms", len(self._chunks), len(self._postings))

    def __len__(self) -> int:
        return len(self._chunks)

    def _idf(self, df: int) -> float:
        n = len(self._chunks)
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Return up to ``top_k`` chunks with a positive BM25 score, best first.

        An empty query, a query with no indexable terms, or an empty index
        yields ``[]``. Ties are broken by original chunk order (deterministic).
        """
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")

        terms = set(tokenize(query, self.config.remove_stopwords))
        if not terms or not self._chunks:
            return []

        k1, b = self.config.k1, self.config.b
        scores: dict[int, float] = defaultdict(float)
        for term in terms:
            postings = self._postings.get(term)
            if not postings:
                continue
            idf = self._idf(len(postings))
            for pos, tf in postings:
                norm = 1.0 - b + b * (self._lengths[pos] / self._avgdl) if self._avgdl else 1.0
                scores[pos] += idf * tf * (k1 + 1.0) / (tf + k1 * norm)

        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        return [SearchResult(self._chunks[pos], score, rank) for rank, (pos, score) in enumerate(ranked, start=1)]
