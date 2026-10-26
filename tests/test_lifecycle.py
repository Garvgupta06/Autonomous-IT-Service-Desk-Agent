from src.tickets.db import init_db
from src.tickets.repository import create_ticket, change_status
from src.tickets.lifecycle import InvalidTransition

init_db()

t = create_ticket("Lifecycle test", reporter="u1")
key = t["key"]

for status in ["in_progress", "waiting_on_user", "in_progress", "resolved", "closed"]:
    print(key, "->", change_status(key, status)["status"])

try:
    change_status(key, "open")
except InvalidTransition as e:
    print("blocked:", e)