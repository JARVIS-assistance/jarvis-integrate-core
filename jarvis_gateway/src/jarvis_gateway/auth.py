import secrets
import time
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException


@dataclass
class Principal:
    user_id: str
    tenant_id: str
    role: str
    token: str


class TokenStore:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self.ttl_seconds = ttl_seconds
        self._tokens: dict[str, tuple[float, dict[str, Any]]] = {}

    def issue(self, user_id: str, tenant_id: str, role: str) -> str:
        token = secrets.token_urlsafe(24)
        self._tokens[token] = (time.time() + self.ttl_seconds, {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": role,
        })
        return token

    def revoke(self, token: str) -> None:
        self._tokens.pop(token, None)

    def get(self, token: str) -> dict[str, Any] | None:
        item = self._tokens.get(token)
        if item is None:
            return None
        expires_at, payload = item
        if time.time() > expires_at:
            self._tokens.pop(token, None)
            return None
        return payload


def parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="invalid authorization header")
    return parts[1]


def get_principal(token_store: TokenStore, authorization: str | None) -> Principal:
    token = parse_bearer_token(authorization)
    payload = token_store.get(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return Principal(
        user_id=payload["user_id"],
        tenant_id=payload["tenant_id"],
        role=payload["role"],
        token=token,
    )


def require_role(principal: Principal, allowed_roles: set[str]) -> None:
    if principal.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="forbidden")


def extract_authorization(authorization: str | None = Header(default=None)) -> str | None:
    return authorization
