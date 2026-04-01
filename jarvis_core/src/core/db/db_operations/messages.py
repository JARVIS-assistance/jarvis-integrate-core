from __future__ import annotations

from uuid import uuid4

from ..db_connection import DBClient
from .common import now_iso


def add_message(db: DBClient, session_id: str, role: str, content: str) -> None:
    message_id = str(uuid4())
    now = now_iso()
    if db.backend == "postgres":
        db.conn.execute(
            "INSERT INTO messages (id, chat_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s)",
            (message_id, session_id, role, content, now),
        )
        db.conn.execute("UPDATE chats SET last_message_at = %s WHERE id = %s", (now, session_id))
    else:
        db.conn.execute(
            "INSERT INTO messages (id, chat_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (message_id, session_id, role, content, now),
        )
        db.conn.execute("UPDATE chats SET last_message_at = ? WHERE id = ?", (now, session_id))
    db.conn.commit()
