"""
Generate evidence-grounded IT support answers using Ollama."""

import json
import urllib.error
import urllib.request

from .retrieval_base import SearchResult


def generate_answer(
    query: str,
    results: list[SearchResult],
    model: str = "llama3.2:3b",
    base_url: str = "http://localhost:11434",
) -> str:
    """Answer a question using retrieved knowledge-base evidence."""

    if not query.strip():
        return "Please enter a question."

    if not results:
        return "I couldn't find relevant information in the knowledge base."

    evidence_parts = []

    for result in results:
        evidence_parts.append(
            f"Source: {result.chunk.source}\n"
            f"Evidence:\n{result.chunk.text}"
        )

    evidence = "\n\n---\n\n".join(evidence_parts)

    prompt = f"""You are an IT support assistant.

Answer the user's specific question clearly and concisely.
Use ONLY the evidence supplied below for troubleshooting instructions.
Do not copy the entire evidence or repeat the documents verbatim.
Give numbered steps when appropriate.
If the evidence does not contain enough information, say so.
Do not invent commands, policies, or troubleshooting steps.
Mention the source filename in your answer.

KNOWLEDGE-BASE EVIDENCE:
{evidence}

USER QUESTION:
{query}

CONCISE ANSWER:"""

    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You provide concise IT support answers grounded "
                        "in supplied evidence."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))

        answer = data.get("message", {}).get("content", "").strip()

        if not answer:
            return "The model returned an empty answer. Please try again."

        return answer

    except urllib.error.HTTPError as exc:
        return f"Ollama API error: HTTP {exc.code}."
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return f"Could not connect to Ollama: {exc}"
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        return f"Could not parse the Ollama response: {exc}"
