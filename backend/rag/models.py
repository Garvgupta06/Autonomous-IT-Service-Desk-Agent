"""Plain data containers shared by the RAG ingestion and chunking stages.

Later stages (BM25, embeddings, hybrid retrieval) should consume ``Chunk``
objects as-is, so the fields here are deliberately small and stable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Document:
    """Text extracted from one knowledge-base file."""

    source: str        # file name, e.g. "vpn_guide.md"
    source_path: str   # path relative to the ingestion root, POSIX style
    file_type: str     # lower-case extension without dot: "txt", "md", "pdf"
    text: str          # normalised text (never empty for a loaded Document)


@dataclass(frozen=True)
class Chunk:
    """A contiguous slice of a Document's text plus provenance metadata."""

    text: str
    source: str        # file name of the originating document
    source_path: str   # relative path (disambiguates identical file names)
    chunk_index: int   # 0-based position within the document
    start_char: int    # offset of ``text`` in the Document text
    end_char: int      # exclusive end offset

    @property
    def chunk_id(self) -> str:
        """Stable identifier, usable as a key by any retriever or index."""
        return f"{self.source_path}#{self.chunk_index}"

    def metadata(self) -> dict[str, Any]:
        """Metadata dict suitable for storing next to an index entry."""
        return {
            "chunk_id": self.chunk_id,
            "source": self.source,
            "source_path": self.source_path,
            "chunk_index": self.chunk_index,
            "start_char": self.start_char,
            "end_char": self.end_char,
        }
