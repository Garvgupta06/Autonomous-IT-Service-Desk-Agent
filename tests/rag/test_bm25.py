import math

import pytest

from backend.rag.bm25 import BM25Config, BM25Retriever, tokenize
from backend.rag.chunking import ChunkingConfig, chunk_documents
from backend.rag.ingestion import ingest_directory
from backend.rag.models import Chunk


def make_chunks(*texts: str) -> list[Chunk]:
    return [Chunk(t, f"doc{i}.txt", f"doc{i}.txt", 0, 0, len(t)) for i, t in enumerate(texts)]


def test_tokenize_lowercases_keeps_codes_and_drops_stopwords():
    assert tokenize("The VPN fails with error 0x80070005!") == ["vpn", "fails", "error", "0x80070005"]
    assert tokenize("the of and") == []
    assert tokenize("The VPN", remove_stopwords=False) == ["the", "vpn"]


def test_exact_error_code_ranks_matching_chunk_first():
    chunks = make_chunks(
        "Printer shows offline. Restart the print spooler service.",
        "Windows update failed with error 0x80070005 access denied.",
        "VPN will not connect after a password change.",
    )
    results = BM25Retriever(chunks).search("error 0x80070005")
    assert results[0].chunk.source == "doc1.txt"
    assert results[0].rank == 1
    assert len(results) == 1                     # only chunks sharing a term are returned


def test_score_matches_bm25_formula():
    chunks = make_chunks("vpn error", "printer offline")
    score = BM25Retriever(chunks).search("vpn")[0].score
    assert score == pytest.approx(math.log(2))   # N=2, df=1, tf=1, |d|=avgdl -> idf only


def test_rare_term_outweighs_common_term():
    chunks = make_chunks("network network network", "network adapter", "network cable", "network switch")
    best = BM25Retriever(chunks).search("network adapter")[0]
    assert best.chunk.source == "doc1.txt"       # "adapter" is rare, so it dominates


def test_no_match_empty_query_and_empty_index_return_empty_list():
    retriever = BM25Retriever(make_chunks("vpn guide"))
    assert retriever.search("zzzz") == []
    assert retriever.search("") == []
    assert retriever.search("the of and") == []
    assert BM25Retriever([]).search("vpn") == []


def test_top_k_limit_ranks_and_deterministic_ties():
    chunks = make_chunks(*["vpn guide"] * 5)     # identical scores
    results = BM25Retriever(chunks).search("vpn", top_k=3)
    assert [r.rank for r in results] == [1, 2, 3]
    assert [r.chunk.source for r in results] == ["doc0.txt", "doc1.txt", "doc2.txt"]


def test_invalid_arguments_are_rejected():
    with pytest.raises(ValueError):
        BM25Config(k1=-1)
    with pytest.raises(ValueError):
        BM25Config(b=1.5)
    with pytest.raises(ValueError):
        BM25Retriever(make_chunks("a b")).search("a", top_k=0)


def test_end_to_end_ingest_chunk_search_keeps_metadata(tmp_path):
    (tmp_path / "vpn.md").write_text("# VPN\n\nIf VPN error 691 appears, re-enter your new password.", encoding="utf-8")
    (tmp_path / "printer.txt").write_text("Printer offline: restart the spooler service.", encoding="utf-8")
    chunks = chunk_documents(ingest_directory(tmp_path).documents, ChunkingConfig(chunk_size=200, chunk_overlap=20))

    top = BM25Retriever(chunks).search("error 691")[0]

    assert top.chunk.source == "vpn.md"
    assert top.chunk.chunk_index == 0
    assert top.chunk.chunk_id == "vpn.md#0"
