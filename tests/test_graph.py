from src.graph import graph

messages = [
    "my VPN keeps disconnecting",
    "please unlock my account",
    "my email is broken",
]

for m in messages:
    result = graph.invoke({
        "user_id": "u1",
        "user_message": m,
        "conversation_history": [],
    })
    print(m, "->", result["detected_intent"], "|", result["response"])