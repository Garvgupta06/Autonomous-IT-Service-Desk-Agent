from backend.rag.generator import generate_answer
from pathlib import Path

from backend.rag.ingestion import ingest_directory
from backend.rag.chunking import chunk_documents
from backend.rag.embedder import OllamaEmbedder
from backend.rag.hybrid import HybridRetriever

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE = ROOT / "data" / "knowledge_base" / "raw"

# Step 1: Ingest documents
result = ingest_directory(KNOWLEDGE_BASE)

print(f"Documents ingested: {len(result.documents)}")
print(f"Files skipped: {len(result.failures)}")

# Step 2: Create chunks
chunks = chunk_documents(result.documents)
print(f"Total chunks created: {len(chunks)}")

if not chunks:
    raise SystemExit("No chunks available. Check the knowledge-base files.")

# Step 3: Build hybrid retriever
print("\nBuilding semantic and keyword retrieval index...")

embedder = OllamaEmbedder(model="nomic-embed-text")
retriever = HybridRetriever(chunks, embedder)

print("RAG retrieval is ready!")

# Step 4: Ask questions
while True:
    query = input("\nAsk an IT support question (or type 'exit'): ").strip()

    if query.lower() in {"exit", "quit"}:
        break

    if not query:
        continue

    try:
        results = retriever.search(query, top_k=3)
    except Exception as exc:
        print(f"Retrieval error: {exc}")
        continue

    if not results:
        print("No relevant information was found in the knowledge base.")
        continue

    print("\n--- AI-Generated IT Support Answer ---")
    answer = generate_answer(query, results)
    print(answer)
    print("\n--- Retrieved Sources ---")
    
    for result in results:
        print(f"- {result.chunk.source} (rank {result.rank})")