import json
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/embed"


def test_embedding_model():
    payload = {
        "model": "nomic-embed-text",
        "input": ["VPN connection fails after Windows restart."]
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))

    embeddings = result["embeddings"]

    assert len(embeddings) == 1
    assert len(embeddings[0]) > 0

    print("\nEmbedding model is working!")
    print(f"Embedding dimensions: {len(embeddings[0])}")


if __name__ == "__main__":
    test_embedding_model()

