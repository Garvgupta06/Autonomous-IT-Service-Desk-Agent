"""Split Document text into overlapping, metadata-carrying chunks.

Sizes are measured in characters, so no tokenizer is required. Chunk ends are
moved back to a natural boundary (paragraph, line, sentence, then word) when one
exists in the second half of the window, which keeps sentences intact more often.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Chunk, Document

# Tried in order; the first separator found closest to the window end wins.
_BREAKS: tuple[str, ...] = ("\n\n", "\n", ". ", "? ", "! ", " ")


@dataclass(frozen=True)
class ChunkingConfig:
    """Chunking parameters (characters)."""

    chunk_size: int = 800
    chunk_overlap: int = 100

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must not be negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")


def _find_end(text: str, start: int, hard_end: int, min_end: int) -> int:
    """Return the best chunk end in [min_end, hard_end]; hard_end if no boundary."""
    for sep in _BREAKS:
        idx = text.rfind(sep, min_end, hard_end)
        if idx != -1:
            return idx + len(sep)
    return hard_end


def chunk_text(
    text: str,
    source: str,
    source_path: str | None = None,
    config: ChunkingConfig | None = None,
) -> list[Chunk]:
    """Chunk raw text. Returns [] for empty/whitespace-only input."""
    cfg = config or ChunkingConfig()
    path = source_path or source
    n = len(text)
    chunks: list[Chunk] = []
    start = 0

    while start < n:
        hard_end = min(start + cfg.chunk_size, n)
        end = hard_end if hard_end == n else _find_end(text, start, hard_end, start + cfg.chunk_size // 2)

        raw = text[start:end]
        stripped = raw.strip()
        if stripped:
            first = start + (len(raw) - len(raw.lstrip()))
            chunks.append(Chunk(stripped, source, path, len(chunks), first, first + len(stripped)))

        if end >= n:
            break

        next_start = end - cfg.chunk_overlap
        if next_start <= start:          # overlap too large for this window: keep moving
            next_start = end
        # Avoid starting mid-word: skip forward to the next word boundary, if any.
        if 0 < next_start < end and not text[next_start - 1].isspace() and not text[next_start].isspace():
            space = text.find(" ", next_start, end)
            if space != -1:
                next_start = space + 1
        start = next_start

    return chunks


def chunk_document(document: Document, config: ChunkingConfig | None = None) -> list[Chunk]:
    """Chunk one Document, carrying its filename and relative path as metadata."""
    return chunk_text(document.text, document.source, document.source_path, config)


def chunk_documents(documents: Iterable[Document], config: ChunkingConfig | None = None) -> list[Chunk]:
    """Chunk many Documents; chunk_index restarts at 0 for each document."""
    chunks: list[Chunk] = []
    for doc in documents:
        chunks.extend(chunk_document(doc, config))
    return chunks
