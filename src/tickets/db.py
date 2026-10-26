import sqlite3
from contextlib import contextmanager
from pathlib import Path

db_path =  Path("data/servicedesk.db")

@contextmanager
def db():
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn =  sqlite3.connect(db_path)
    conn.row_factory=sqlite3.Row

    try:
        yield conn
        conn.commit()                 
    except Exception:
        conn.rollback()                
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                key         TEXT UNIQUE,
                title       TEXT NOT NULL,
                description TEXT,
                category    TEXT,
                priority    TEXT NOT NULL DEFAULT 'medium',
                status      TEXT NOT NULL DEFAULT 'open',
                reporter    TEXT NOT NULL,
                assignee    TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)