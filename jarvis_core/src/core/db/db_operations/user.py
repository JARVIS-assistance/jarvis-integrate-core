from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Any, Optional
from uuid import uuid4

from ..db_connection import DBClient
from .common import now_iso


def _hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt_bytes = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt_bytes, n=2**14, r=8, p=1, dklen=32)
    return f"{base64.urlsafe_b64encode(salt_bytes).decode()}${base64.urlsafe_b64encode(dk).decode()}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        salt_b64, digest_b64 = password_hash.split("$", 1)
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
    except Exception:
        return False

    actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(actual, expected)


def create_user_with_password(
    db: DBClient, email: str, password: str, name: Optional[str], role: str = "USER"
) -> dict[str, Any]:
    user_id = str(uuid4())
    persona_id = str(uuid4())
    user_persona_id = str(uuid4())
    chat_id = str(uuid4())
    password_hash = _hash_password(password)
    now = now_iso()
    persona_name = "Default Persona"
    persona_description = "Auto-created default persona per user."
    persona_prompt = "You are Jarvis, a practical and concise assistant for this user."
    persona_tone = "balanced"
    persona_alias = "default"

    try:
        if db.backend == "postgres":
            db.conn.execute(
                """
                INSERT INTO users (id, email, name, status, created_at, updated_at)
                VALUES (%s, %s, %s, 'ACTIVE', %s, %s)
                """,
                (user_id, email, name, now, now),
            )
            db.conn.execute(
                """
                INSERT INTO auth_identities (user_id, password_hash, role, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, true, %s, %s)
                """,
                (user_id, password_hash, role, now, now),
            )
            db.conn.execute(
                """
                INSERT INTO personas (id, owner_user_id, name, description, prompt_template, tone, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, true)
                """,
                (persona_id, user_id, persona_name, persona_description, persona_prompt, persona_tone),
            )
            db.conn.execute(
                """
                INSERT INTO user_personas (id, user_id, persona_id, alias)
                VALUES (%s, %s, %s, %s)
                """,
                (user_persona_id, user_id, persona_id, persona_alias),
            )
            db.conn.execute(
                """
                INSERT INTO chats (id, user_id, status, last_selected_user_persona_id, created_at, last_message_at)
                VALUES (%s, %s, 'ACTIVE', %s, %s, %s)
                """,
                (chat_id, user_id, user_persona_id, now, now),
            )
        else:
            db.conn.execute(
                """
                INSERT INTO users (id, email, name, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, email, name, "ACTIVE", now, now),
            )
            db.conn.execute(
                """
                INSERT INTO auth_identities (user_id, password_hash, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, password_hash, role, 1, now, now),
            )
            db.conn.execute(
                """
                INSERT INTO personas (id, owner_user_id, name, description, prompt_template, tone, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (persona_id, user_id, persona_name, persona_description, persona_prompt, persona_tone, 1),
            )
            db.conn.execute(
                """
                INSERT INTO user_personas (id, user_id, persona_id, alias)
                VALUES (?, ?, ?, ?)
                """,
                (user_persona_id, user_id, persona_id, persona_alias),
            )
            db.conn.execute(
                """
                INSERT INTO chats (id, user_id, status, last_selected_user_persona_id, created_at, last_message_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chat_id, user_id, "ACTIVE", user_persona_id, now, now),
            )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    return {"id": user_id, "email": email, "name": name, "role": role}


def find_user_by_email(db: DBClient, email: str) -> Optional[dict[str, Any]]:
    if db.backend == "postgres":
        cursor = db.conn.execute(
            """
            SELECT u.id, u.email, u.name, u.status, a.password_hash, a.role, a.is_active
            FROM users u
            JOIN auth_identities a ON a.user_id = u.id
            WHERE u.email = %s
            """,
            (email,),
        )
    else:
        cursor = db.conn.execute(
            """
            SELECT u.id, u.email, u.name, u.status, a.password_hash, a.role, a.is_active
            FROM users u
            JOIN auth_identities a ON a.user_id = u.id
            WHERE u.email = ?
            """,
            (email,),
        )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "id": str(row[0]),
        "email": row[1],
        "name": row[2],
        "status": row[3],
        "password_hash": row[4],
        "role": row[5],
        "is_active": bool(row[6]),
    }


def authenticate_user(db: DBClient, email: str, password: str) -> Optional[dict[str, Any]]:
    user = find_user_by_email(db, email)
    if user is None:
        return None
    if user["status"] != "ACTIVE" or not user["is_active"]:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}


def find_user_by_id(db: DBClient, user_id: str) -> Optional[dict[str, Any]]:
    if db.backend == "postgres":
        cursor = db.conn.execute(
            """
            SELECT u.id, u.email, u.name, u.status, a.role, a.is_active
            FROM users u
            LEFT JOIN auth_identities a ON a.user_id = u.id
            WHERE u.id = %s
            """,
            (user_id,),
        )
    else:
        cursor = db.conn.execute(
            """
            SELECT u.id, u.email, u.name, u.status, a.role, a.is_active
            FROM users u
            LEFT JOIN auth_identities a ON a.user_id = u.id
            WHERE u.id = ?
            """,
            (user_id,),
        )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "id": str(row[0]),
        "email": row[1],
        "name": row[2],
        "status": row[3],
        "role": row[4] or "USER",
        "is_active": bool(row[5]) if row[5] is not None else True,
    }
