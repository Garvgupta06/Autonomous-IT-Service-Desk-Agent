from src.graph import graph

def chat(thread, user, msg):
    out = graph.invoke({"user_id": user, "user_message": msg},
                       {"configurable": {"thread_id": thread}})
    print(f"[{user}] {msg}\n   -> {out['response']}\n")

chat("t1", "u1", "please unlock my account")
chat("t1", "u1", "yes")
chat("t2", "u1", "give me access to Jira")      # employee: should be denied
chat("t3", "u2", "give me access to Jira")      # admin: should be proposed
chat("t3", "u2", "no")