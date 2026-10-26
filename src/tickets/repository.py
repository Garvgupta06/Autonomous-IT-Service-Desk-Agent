from datetime import datetime, timezone
from src.tickets.db import db
from src.tickets.lifecycle  import check_transition

VALID_PRIORITIES = {"low", "medium", "high", "critical"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_ticket(title, reporter, description="", category=None,
                  priority="medium") -> dict:
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"priority must be one of {VALID_PRIORITIES}")
    now = _now()
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO tickets
               (title, description, category, priority, reporter, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, description, category, priority, reporter, now, now),
        )
        key = f"DESK-{cur.lastrowid}"
        conn.execute("UPDATE tickets SET key = ? WHERE id = ?", (key, cur.lastrowid))
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_ticket(key: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE key = ?", (key,)).fetchone()
    return dict(row) if row else None


def list_tickets(reporter: str | None = None, status: str | None = None) -> list[dict]:
    query, params = "SELECT * FROM tickets WHERE 1=1", []
    if reporter:
        query += " AND reporter = ?"
        params.append(reporter)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC"
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]

def change_status(key:str , new_status:str) -> dict:
    with db() as conn:
        row = conn.execute("SELECT status FROM tickets where key = ?", (key,)).fetchone()
        if row is None:
            raise KeyError(f"No Ticket {key}")
        check_transition(row["status"], new_status)

        conn.execute(
            "UPDATE tickets SET status =?, updated_at=? WHERE key=?",(new_status,_now(),key),
        )
        updated = conn.execute("SELECT * FROM tickets WHERE key = ?",(key,)).fetchone()
        return dict(updated)

    