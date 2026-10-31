from backend.rag.chunking import chunk_text
from backend.rag.embedder import OllamaEmbedder
from backend.rag.hybrid import HybridRetriever
from backend.rag.models import Chunk


def test_hybrid_retrieval_returns_ranked_results():
    chunks = [
        Chunk(
            text="VPN connection fails when network settings are incorrect.",
            source="vpn.md",
            source_path="vpn.md",
            chunk_index=0,
            start_char=0,
            end_char=60,
        ),
        Chunk(
            text="Windows Update errors can occur when updates remain pending.",
            source="windows.md",
            source_path="windows.md",
            chunk_index=0,
            start_char=0,
            end_char=59,
        ),
    ]

    retriever = HybridRetriever(
        chunks,
        OllamaEmbedder(),
    )

    results = retriever.search(
        "VPN connection failure",
        top_k=2,
    )

    assert results
    assert results[0].rank == 1
    assert results[0].chunk.source == "vpn.md"