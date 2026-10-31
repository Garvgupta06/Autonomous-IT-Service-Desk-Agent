from src.graph import graph
cfg = {"configurable": {"thread_id": "demo"}}
r = graph.invoke({"user_id": "u1", "user_message": "my laptop is very slow"}, cfg)
print(r["response"]); print("pending:", r.get("pending_action"))
r = graph.invoke({"user_id": "u1", "user_message": "yes"}, cfg)
print(r["response"])