"""Common result type and interface for all retrievers.

BM25 (this stage), semantic retrieval and hybrid fusion (later stages) all
return ``list[SearchResult]`` and expose ``search(query, top_k)``, so they can be
swapped or combined without changing callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import Chunk


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float   # retriever-specific scale; only compare within one retriever
    rank: int      # 1-based position in the returned list


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Return up to ``top_k`` results, best first."""
        ...
