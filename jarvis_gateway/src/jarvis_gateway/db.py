from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_SRC = REPO_ROOT / "jarvis_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from core.db.db import (  # noqa: E402
    DBClient,
    authenticate_user,
    connect as connect_core,
    create_user_with_password,
    find_user_by_email,
    init_db as init_core_db,
)
from core.db.db_operations.common import now_iso  # noqa: E402


DEFAULT_TENANT_ID = "tenant-default"
DEFAULT_TENANT_NAME = "Default Tenant"
DEFAULT_ADMIN_EMAIL = "admin@jarvis.local"


def _placeholder(db: DBClient) -> str:
    return "%s" if db.backend == "postgres" else "?"


def _username_to_email(username: str) -> str:
    normalized = username.strip()
    if "@" in normalized:
        return normalized.lower()
    return f"{normalized.lower()}@jarvis.local"


def _email_to_username(email: str) -> str:
    return email.split("@", 1)[0]


def _fetchone_as_dict(cursor: Any) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return dict(row)
    return dict(zip([column[0] for column in cursor.description], row))


def _ensure_gateway_tables(db: DBClient) -> None:
    if db.backend == "postgres":
        db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gateway_tenants (
                id text PRIMARY KEY,
                name text NOT NULL,
                created_at timestamptz NOT NULL
            )
            """
        )
        db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gateway_user_tenants (
                user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                tenant_id text NOT NULL REFERENCES gateway_tenants(id) ON DELETE CASCADE,
                created_at timestamptz NOT NULL
            )
            """
        )
        db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gateway_chat_meta (
                chat_id uuid PRIMARY KEY REFERENCES chats(id) ON DELETE CASCADE,
                tenant_id text NOT NULL REFERENCES gateway_tenants(id) ON DELETE CASCADE,
                title text NOT NULL,
                created_at timestamptz NOT NULL,
                updated_at timestamptz NOT NULL
            )
            """
        )
        db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gateway_audit_logs (
                id bigserial PRIMARY KEY,
                request_id text NOT NULL,
                actor_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tenant_id text NOT NULL REFERENCES gateway_tenants(id) ON DELETE CASCADE,
                action text NOT NULL,
                resource text NOT NULL,
                status text NOT NULL,
                detail text NOT NULL,
                created_at timestamptz NOT NULL
            )
            """
        )
    else:
        db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS gateway_tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS gateway_user_tenants (
                user_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(tenant_id) REFERENCES gateway_tenants(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS gateway_chat_meta (
                chat_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                FOREIGN KEY(tenant_id) REFERENCES gateway_tenants(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS gateway_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                actor_user_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(actor_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(tenant_id) REFERENCES gateway_tenants(id) ON DELETE CASCADE
            );
            """
        )
    db.conn.commit()


def _ensure_default_tenant(db: DBClient) -> None:
    placeholder = _placeholder(db)
    query = f"SELECT id, name, created_at FROM gateway_tenants WHERE id = {placeholder}"
    if _fetchone_as_dict(db.conn.execute(query, (DEFAULT_TENANT_ID,))) is not None:
        return

    now = now_iso()
    insert = (
        "INSERT INTO gateway_tenants (id, name, created_at) VALUES "
        f"({placeholder}, {placeholder}, {placeholder})"
    )
    db.conn.execute(insert, (DEFAULT_TENANT_ID, DEFAULT_TENANT_NAME, now))
    db.conn.commit()


def _ensure_user_tenant(db: DBClient, user_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> None:
    placeholder = _placeholder(db)
    lookup = f"SELECT user_id FROM gateway_user_tenants WHERE user_id = {placeholder}"
    if _fetchone_as_dict(db.conn.execute(lookup, (user_id,))) is not None:
        return

    now = now_iso()
    insert = (
        "INSERT INTO gateway_user_tenants (user_id, tenant_id, created_at) VALUES "
        f"({placeholder}, {placeholder}, {placeholder})"
    )
    db.conn.execute(insert, (user_id, tenant_id, now))
    db.conn.commit()


def connect(db_path: str | None = None) -> DBClient:
    return connect_core(db_path)


def init_db(db: DBClient) -> None:
    init_core_db(db)
    _ensure_gateway_tables(db)
    _ensure_default_tenant(db)


def seed_admin(db: DBClient) -> None:
    _ensure_default_tenant(db)
    user = find_user_by_email(db, DEFAULT_ADMIN_EMAIL)
    if user is None:
        created = create_user_with_password(
            db,
            email=DEFAULT_ADMIN_EMAIL,
            password="admin123",
            name="Admin",
            role="admin",
        )
        user_id = created["id"]
    else:
        user_id = user["id"]
    _ensure_user_tenant(db, user_id, DEFAULT_TENANT_ID)


def create_tenant(db: DBClient, name: str) -> dict[str, Any]:
    tenant_id = f"tenant-{uuid4()}"
    created_at = now_iso()
    placeholder = _placeholder(db)
    query = (
        "INSERT INTO gateway_tenants (id, name, created_at) VALUES "
        f"({placeholder}, {placeholder}, {placeholder})"
    )
    db.conn.execute(query, (tenant_id, name, created_at))
    db.conn.commit()
    return {"id": tenant_id, "name": name, "created_at": created_at}


def get_tenant(db: DBClient, tenant_id: str) -> dict[str, Any] | None:
    placeholder = _placeholder(db)
    cursor = db.conn.execute(
        f"SELECT id, name, created_at FROM gateway_tenants WHERE id = {placeholder}",
        (tenant_id,),
    )
    return _fetchone_as_dict(cursor)


def create_user(db: DBClient, tenant_id: str, username: str, password: str, role: str) -> dict[str, Any]:
    email = _username_to_email(username)
    existing = find_user_by_email(db, email)
    if existing is not None:
        raise ValueError("user already exists")

    created = create_user_with_password(
        db,
        email=email,
        password=password,
        name=username,
        role=role,
    )
    _ensure_user_tenant(db, created["id"], tenant_id)
    return {
        "id": created["id"],
        "tenant_id": tenant_id,
        "username": username,
        "role": role,
        "created_at": now_iso(),
    }


def get_user(db: DBClient, user_id: str) -> dict[str, Any] | None:
    placeholder = _placeholder(db)
    cursor = db.conn.execute(
        f"""
        SELECT u.id, u.email, u.name, a.role, u.created_at, gut.tenant_id
        FROM users u
        LEFT JOIN auth_identities a ON a.user_id = u.id
        LEFT JOIN gateway_user_tenants gut ON gut.user_id = u.id
        WHERE u.id = {placeholder}
        """,
        (user_id,),
    )
    row = _fetchone_as_dict(cursor)
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "tenant_id": row["tenant_id"] or DEFAULT_TENANT_ID,
        "username": _email_to_username(str(row["email"])),
        "role": row["role"] or "USER",
        "created_at": str(row["created_at"]),
    }


def find_user_by_credentials(db: DBClient, username: str, password: str) -> dict[str, Any] | None:
    email = _username_to_email(username)
    user = authenticate_user(db, email, password)
    if user is None:
        return None
    _ensure_user_tenant(db, user["id"], DEFAULT_TENANT_ID)

    placeholder = _placeholder(db)
    cursor = db.conn.execute(
        f"SELECT tenant_id FROM gateway_user_tenants WHERE user_id = {placeholder}",
        (user["id"],),
    )
    tenant = _fetchone_as_dict(cursor)
    return {
        "id": user["id"],
        "tenant_id": (tenant or {}).get("tenant_id", DEFAULT_TENANT_ID),
        "username": _email_to_username(user["email"]),
        "role": user["role"],
    }


def create_session(db: DBClient, tenant_id: str, user_id: str, title: str) -> dict[str, Any]:
    session_id = str(uuid4())
    now = now_iso()
    placeholder = _placeholder(db)

    if db.backend == "postgres":
        db.conn.execute(
            """
            INSERT INTO chats (id, user_id, status, created_at, last_message_at)
            VALUES (%s, %s, 'ACTIVE', %s, %s)
            """,
            (session_id, user_id, now, now),
        )
        db.conn.execute(
            """
            INSERT INTO gateway_chat_meta (chat_id, tenant_id, title, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (session_id, tenant_id, title, now, now),
        )
    else:
        db.conn.execute(
            """
            INSERT INTO chats (id, user_id, status, created_at, last_message_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, user_id, "ACTIVE", now, now),
        )
        db.conn.execute(
            """
            INSERT INTO gateway_chat_meta (chat_id, tenant_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, tenant_id, title, now, now),
        )
    db.conn.commit()
    return {
        "id": session_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "title": title,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }


def get_session(db: DBClient, session_id: str) -> dict[str, Any] | None:
    placeholder = _placeholder(db)
    cursor = db.conn.execute(
        f"""
        SELECT c.id, c.user_id, c.status, c.created_at, c.last_message_at, gcm.tenant_id, gcm.title
        FROM chats c
        LEFT JOIN gateway_chat_meta gcm ON gcm.chat_id = c.id
        WHERE c.id = {placeholder}
        """,
        (session_id,),
    )
    row = _fetchone_as_dict(cursor)
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "tenant_id": row["tenant_id"] or DEFAULT_TENANT_ID,
        "user_id": str(row["user_id"]),
        "title": row["title"] or "new session",
        "status": "terminated" if row["status"] != "ACTIVE" else "active",
        "created_at": str(row["created_at"]),
        "updated_at": str(row["last_message_at"]),
    }


def terminate_session(db: DBClient, session_id: str) -> dict[str, Any] | None:
    current = get_session(db, session_id)
    if current is None:
        return None

    now = now_iso()
    placeholder = _placeholder(db)
    if db.backend == "postgres":
        db.conn.execute(
            "UPDATE chats SET status = 'ARCHIVED', last_message_at = %s WHERE id = %s",
            (now, session_id),
        )
        db.conn.execute(
            "UPDATE gateway_chat_meta SET updated_at = %s WHERE chat_id = %s",
            (now, session_id),
        )
    else:
        db.conn.execute(
            "UPDATE chats SET status = ?, last_message_at = ? WHERE id = ?",
            ("ARCHIVED", now, session_id),
        )
        db.conn.execute(
            f"UPDATE gateway_chat_meta SET updated_at = {placeholder} WHERE chat_id = {placeholder}",
            (now, session_id),
        )
    db.conn.commit()
    return {"id": session_id, "status": "terminated", "updated_at": now}


def add_audit_log(
    db: DBClient,
    request_id: str,
    actor_user_id: str,
    tenant_id: str,
    action: str,
    resource: str,
    status: str,
    detail: str,
) -> None:
    now = now_iso()
    if db.backend == "postgres":
        db.conn.execute(
            """
            INSERT INTO gateway_audit_logs (
                request_id, actor_user_id, tenant_id, action, resource, status, detail, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (request_id, actor_user_id, tenant_id, action, resource, status, detail, now),
        )
    else:
        db.conn.execute(
            """
            INSERT INTO gateway_audit_logs (
                request_id, actor_user_id, tenant_id, action, resource, status, detail, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (request_id, actor_user_id, tenant_id, action, resource, status, detail, now),
        )
    db.conn.commit()


def list_audit_logs(db: DBClient, tenant_id: str, limit: int) -> list[dict[str, Any]]:
    placeholder = _placeholder(db)
    cursor = db.conn.execute(
        f"""
        SELECT id, action, resource, status, detail, request_id, actor_user_id, tenant_id, created_at
        FROM gateway_audit_logs
        WHERE tenant_id = {placeholder}
        ORDER BY id DESC
        LIMIT {placeholder}
        """,
        (tenant_id, limit),
    )
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], "keys"):
        return [dict(row) for row in rows]
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]
