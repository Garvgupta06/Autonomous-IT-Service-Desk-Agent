import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from backend.rag import service
from backend.rag.embedder import EmbeddingError
from backend.rag.models import Chunk
from backend.rag.retrieval_base import SearchResult

ROOT = Path(__file__).resolve().parents[2]


class FakeEmbedder:
    """Concept-style fake: no Ollama needed."""
    CONCEPTS = {"vpn": 0, "network": 0, "connect": 0, "printer": 1, "spooler": 1, "print": 1}

    def __init__(self, *args, **kwargs):
        pass

    def _vec(self, text):
        v = np.zeros(2, dtype=np.float32)
        for w in text.lower().replace(":", " ").split():
            if w in self.CONCEPTS:
                v[self.CONCEPTS[w]] += 1
        return v

    def embed_documents(self, texts):
        return np.stack([self._vec(t) for t in texts])

    def embed_query(self, text):
        return self._vec(text)


class FakeHybrid:
    builds = 0

    def __init__(self, chunks, embedder):
        type(self).builds += 1
        self.chunks = chunks
        self.last_top_k = None

    def search(self, query, top_k=5):
        self.last_top_k = top_k
        return [SearchResult(c, 1.0 / (i + 1), i + 1) for i, c in enumerate(self.chunks[:top_k])]


def prepare(monkeypatch, tmp_path, files=None, hybrid=FakeHybrid):
    for name, text in (files if files is not None else {"vpn.md": "VPN error 691 fix", "printer.md": "Printer spooler stuck"}).items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    monkeypatch.setattr(service, "KNOWLEDGE_BASE", tmp_path)
    monkeypatch.setattr(service, "OllamaEmbedder", FakeEmbedder)
    monkeypatch.setattr(service, "HybridRetriever", hybrid)
    FakeHybrid.builds = 0
    service.reset_retriever()


def test_retrieve_returns_required_fields(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    hits = service.retrieve("vpn error", top_k=2)
    assert len(hits) == 2
    for hit in hits:
        assert set(hit) == {"text", "source", "chunk_id", "score"}
        assert isinstance(hit["text"], str) and hit["text"]
        assert hit["source"].endswith(".md")
        assert hit["chunk_id"].endswith("#0")
        assert isinstance(hit["score"], float)
    assert hits[0]["score"] >= hits[1]["score"]


def test_retriever_is_built_once_and_reused(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    service.retrieve("vpn")
    service.retrieve("printer")
    assert FakeHybrid.builds == 1


def test_top_k_is_forwarded_and_validated(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    assert len(service.retrieve("vpn", top_k=1)) == 1
    assert service.get_retriever().last_top_k == 1
    assert len(service.retrieve("vpn")) == 2          # default top_k=3, only 2 chunks exist
    with pytest.raises(ValueError):
        service.retrieve("vpn", top_k=0)


def test_blank_query_returns_empty_without_building(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    assert service.retrieve("") == []
    assert service.retrieve("   \n") == []
    assert FakeHybrid.builds == 0


def test_empty_knowledge_base_raises_and_failure_is_not_cached(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path, files={})
    with pytest.raises(service.RetrievalUnavailableError):
        service.retrieve("vpn")
    (tmp_path / "vpn.md").write_text("VPN error 691 fix", encoding="utf-8")
    assert service.retrieve("vpn")[0]["source"] == "vpn.md"      # retried and succeeded


def test_missing_knowledge_base_directory_raises(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(service, "KNOWLEDGE_BASE", tmp_path / "does_not_exist")
    with pytest.raises(service.RetrievalUnavailableError):
        service.retrieve("vpn")


def test_ollama_unavailable_gives_clear_error_and_retries(monkeypatch, tmp_path):
    class DownHybrid(FakeHybrid):
        down = True

        def __init__(self, chunks, embedder):
            if DownHybrid.down:
                raise EmbeddingError("connection refused")
            super().__init__(chunks, embedder)

    prepare(monkeypatch, tmp_path, hybrid=DownHybrid)
    with pytest.raises(service.RetrievalUnavailableError):
        service.retrieve("vpn")
    DownHybrid.down = False                                         # Ollama "started"
    assert service.retrieve("vpn")


def test_real_hybrid_retriever_over_real_files_with_mocked_embeddings(monkeypatch, tmp_path):
    from backend.rag.hybrid import HybridRetriever
    prepare(monkeypatch, tmp_path, hybrid=HybridRetriever)
    hits = service.retrieve("vpn error 691", top_k=2)
    assert hits[0]["source"] == "vpn.md"
    assert hits[0]["chunk_id"] == "vpn.md#0"


def test_importing_service_does_not_start_the_cli():
    code = "import sys, backend.rag.service; assert 'backend.rag.run_pipeline' not in sys.modules; print('imported')"
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "imported"        # nothing else printed, no prompt, no hang
