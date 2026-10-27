from src.tickets.db import init_db
from src.tickets.repository import create_ticket, get_ticket, list_tickets

init_db()

t = create_ticket("VPN keeps disconnecting", reporter="u1",
                  category="vpn", priority="high")
print("created:", t)
print("fetched:", get_ticket(t["key"]))
print("u1 has", len(list_tickets(reporter="u1")), "ticket(s)")