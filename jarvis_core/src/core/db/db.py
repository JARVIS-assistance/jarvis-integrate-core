from __future__ import annotations

from .db_connection import DBClient, connect, get_database_url, get_db_path
from .db_operations import (
    add_message,
    authenticate_user,
    create_user_model_config,
    create_session,
    create_user_with_password,
    ensure_user_exists,
    find_user_by_email,
    find_user_by_id,
    get_active_model_for_user,
    get_model_config_by_id_for_user,
    get_or_create_session_for_user,
    get_session,
    get_user_ai_selection,
    list_user_model_configs,
    now_iso,
    set_user_ai_selection,
)
from .db_schema import init_db

__all__ = [
    "DBClient",
    "add_message",
    "authenticate_user",
    "connect",
    "create_user_model_config",
    "create_session",
    "create_user_with_password",
    "ensure_user_exists",
    "find_user_by_email",
    "find_user_by_id",
    "get_database_url",
    "get_db_path",
    "get_active_model_for_user",
    "get_model_config_by_id_for_user",
    "get_or_create_session_for_user",
    "get_session",
    "get_user_ai_selection",
    "list_user_model_configs",
    "init_db",
    "now_iso",
    "set_user_ai_selection",
]
