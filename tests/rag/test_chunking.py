import pytest

from backend.rag.chunking import ChunkingConfig, chunk_document, chunk_documents, chunk_text
from backend.rag.models import Document


def words(n: int) -> str:
    return " ".join(f"word{i}" for i in range(n))


def test_short_text_gives_single_chunk_with_metadata():
    chunks = chunk_text("Short note.", "note.txt", "kb/note.txt")
    assert len(chunks) == 1
    c = chunks[0]
    assert (c.source, c.source_path, c.chunk_index) == ("note.txt", "kb/note.txt", 0)
    assert c.chunk_id == "kb/note.txt#0"
    assert c.metadata()["source"] == "note.txt"


def test_chunks_respect_size_index_and_offsets():
    text = words(300)
    cfg = ChunkingConfig(chunk_size=200, chunk_overlap=40)
    chunks = chunk_text(text, "big.txt", config=cfg)
    assert len(chunks) > 1
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    for c in chunks:
        assert len(c.text) <= 200
        assert text[c.start_char:c.end_char] == c.text      # offsets map back to the source
    assert chunks[-1].end_char == len(text)                 # nothing lost at the end


def test_consecutive_chunks_overlap():
    text = words(300)
    chunks = chunk_text(text, "big.txt", config=ChunkingConfig(chunk_size=200, chunk_overlap=40))
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.start_char < prev.end_char               # shared text
        assert nxt.start_char > prev.start_char             # always moves forward


def test_large_overlap_still_terminates_and_covers_text():
    text = "x" * 95
    chunks = chunk_text(text, "t.txt", config=ChunkingConfig(chunk_size=10, chunk_overlap=9))
    assert chunks[-1].end_char == 95
    assert len(chunks) < 200


def test_empty_or_whitespace_text_gives_no_chunks():
    assert chunk_text("", "e.txt") == []
    assert chunk_text("  \n\n  ", "e.txt") == []


def test_invalid_config_is_rejected():
    for size, overlap in [(0, 0), (-5, 0), (100, -1), (100, 100), (100, 150)]:
        with pytest.raises(ValueError):
            ChunkingConfig(chunk_size=size, chunk_overlap=overlap)


def test_chunk_documents_keeps_per_document_metadata():
    docs = [
        Document("a.txt", "a.txt", "txt", words(100)),
        Document("b.md", "sub/b.md", "md", words(100)),
    ]
    chunks = chunk_documents(docs, ChunkingConfig(chunk_size=200, chunk_overlap=20))
    by_source = {s: [c for c in chunks if c.source == s] for s in ("a.txt", "b.md")}
    assert all(by_source.values())
    assert by_source["b.md"][0].chunk_index == 0                       # index restarts per document
    assert {c.source_path for c in by_source["b.md"]} == {"sub/b.md"}
    assert len({c.chunk_id for c in chunks}) == len(chunks)            # ids are unique


def test_chunk_document_default_config_is_800_100():
    cfg = ChunkingConfig()
    assert (cfg.chunk_size, cfg.chunk_overlap) == (800, 100)
    doc = Document("a.txt", "a.txt", "txt", words(400))
    assert all(len(c.text) <= 800 for c in chunk_document(doc))
