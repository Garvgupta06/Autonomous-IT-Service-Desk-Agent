from src.orchestrator.classifier import classify_intent

messages = [
    "my VPN keeps disconnecting",
    "please unlock my account",
    "my email is broken",
    "can you grant me access to Slack",
]

for m in messages:
    print(m, "->", classify_intent({"user_message": m}))