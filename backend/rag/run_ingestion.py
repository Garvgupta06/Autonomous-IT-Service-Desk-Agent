
from pathlib import Path

from backend.rag.ingestion import ingest_directory

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE = ROOT / "data" / "knowledge_base" / "raw"

result = ingest_directory(KNOWLEDGE_BASE)

print(f"\nDocuments successfully ingested: {len(result.documents)}")
print(f"Files skipped: {len(result.failures)}")

for document in result.documents:
    print(f"\nSource: {document.source}")
    print(f"Type: {document.file_type}")
    print(f"Extracted characters: {len(document.text)}")
    print(f"Preview: {document.text[:200]}")

for failure in result.failures:
    print(f"\nFailed: {failure.path}")
    print(f"Reason: {failure.reason}")
