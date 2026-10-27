import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

from backend.rag.embedder import EmbeddingError, OllamaEmbedder
from backend.rag.models import Chunk
from backend.rag.semantic import SemanticRetriever

# --------------------------------------------------------------------------- #
# Fake embedder: words map to "concept" dimensions, so a paraphrase with NO
# shared words still lands near the right chunk (what real embeddings provide).
# --------------------------------------------------------------------------- #
CONCEPTS = {
    "network": 0, "vpn": 0, "connect": 0, "office": 0, "remote": 0,
    "printer": 1, "print": 1, "paper": 1, "spooler": 1,
    "password": 2, "login": 2, "credentials": 2,
}


class FakeEmbedder:
    def __init__(self):
        self.query_calls = 0

    def _vec(self, text):
        v = np.zeros(3, dtype=np.float32)
        for w in text.lower().split():
            if w in CONCEPTS:
                v[CONCEPTS[w]] += 1
        return v

    def embed_documents(self, texts):
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, 0), dtype=np.float32)

    def embed_query(self, text):
        self.query_calls += 1
        return self._vec(text)


def make_chunks(*texts):
    return [Chunk(t, f"doc{i}.txt", f"doc{i}.txt", 0, 0, len(t)) for i, t in enumerate(texts)]


KB = make_chunks("vpn will not connect", "printer spooler stuck", "password login credentials reset")


def test_paraphrase_query_finds_right_chunk_and_scores_are_cosine():
    results = SemanticRetriever(KB, FakeEmbedder()).search("remote office network")   # no word shared with chunk 0
    assert results[0].chunk.source == "doc0.txt"
    assert results[0].rank == 1
    assert results[0].score == pytest.approx(1.0)       # same direction -> cosine 1
    assert results[1].score == pytest.approx(0.0, abs=1e-6)


def test_top_k_min_score_and_deterministic_ties():
    r = SemanticRetriever(KB, FakeEmbedder(), min_score=0.5).search("vpn", top_k=3)
    assert [x.chunk.source for x in r] == ["doc0.txt"]                  # others fall below min_score
    tied = SemanticRetriever(make_chunks("vpn a", "vpn b", "vpn c"), FakeEmbedder()).search("vpn", top_k=2)
    assert [x.chunk.source for x in tied] == ["doc0.txt", "doc1.txt"]


def test_empty_query_and_empty_index_do_not_call_embedder():
    emb = FakeEmbedder()
    assert SemanticRetriever(KB, emb).search("   ") == []
    assert SemanticRetriever([], emb).search("vpn") == []
    assert emb.query_calls == 0
    assert SemanticRetriever(KB, emb).search("zzz unknown words") == []   # zero vector -> no NaN, no results


def test_invalid_top_k_and_bad_embedder_output_raise():
    with pytest.raises(ValueError):
        SemanticRetriever(KB, FakeEmbedder()).search("vpn", top_k=0)

    class WrongCount(FakeEmbedder):
        def embed_documents(self, texts):
            return super().embed_documents(texts)[:-1]

    with pytest.raises(EmbeddingError):
        SemanticRetriever(KB, WrongCount())

    class WrongDim(FakeEmbedder):
        def embed_query(self, text):
            return np.ones(5, dtype=np.float32)

    with pytest.raises(EmbeddingError):
        SemanticRetriever(KB, WrongDim()).search("vpn")


# --------------------------------------------------------------------------- #
# OllamaEmbedder against a local stub HTTP server (no real Ollama needed)
# --------------------------------------------------------------------------- #
class StubOllama:
    """Context manager running a tiny /api/embed server on a free port."""

    def __init__(self, status=200, body=None):
        self.requests = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stub.requests.append((self.path, payload))
                if status != 200:
                    self.send_response(status); self.end_headers(); return
                reply = body if body is not None else {"embeddings": [[1.0, 2.0, 3.0] for _ in payload["input"]]}
                data = json.dumps(reply).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown(); self.server.server_close()


def test_ollama_embedder_batches_and_applies_prefixes():
    with StubOllama() as stub:
        emb = OllamaEmbedder(base_url=stub.url, batch_size=2)
        docs = emb.embed_documents(["a", "b", "c"])
        query = emb.embed_query("q")
    assert docs.shape == (3, 3) and query.shape == (3,)
    assert len(stub.requests) == 3                                   # 2 doc batches + 1 query
    assert stub.requests[0][0] == "/api/embed"
    assert stub.requests[0][1] == {"model": "nomic-embed-text", "input": ["search_document: a", "search_document: b"]}
    assert stub.requests[2][1]["input"] == ["search_query: q"]


def test_ollama_embedder_errors_are_wrapped():
    with StubOllama(status=404) as stub:
        with pytest.raises(EmbeddingError):
            OllamaEmbedder(base_url=stub.url).embed_query("q")
    with StubOllama(body={"unexpected": 1}) as stub:
        with pytest.raises(EmbeddingError):
            OllamaEmbedder(base_url=stub.url).embed_query("q")
    with StubOllama() as stub:
        closed_url = stub.url                                        # server stopped after the with-block
    with pytest.raises(EmbeddingError):
        OllamaEmbedder(base_url=closed_url, timeout=2).embed_query("q")


def test_semantic_retriever_works_with_ollama_embedder_over_http():
    vectors = {"search_document: vpn": [1.0, 0.0], "search_document: printer": [0.0, 1.0], "search_query: vpn": [1.0, 0.1]}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            data = json.dumps({"embeddings": [vectors[t] for t in payload["input"]]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        emb = OllamaEmbedder(base_url=f"http://127.0.0.1:{server.server_port}")
        top = SemanticRetriever(make_chunks("vpn", "printer"), emb).search("vpn")[0]
    finally:
        server.shutdown(); server.server_close()
    assert top.chunk.source == "doc0.txt"
