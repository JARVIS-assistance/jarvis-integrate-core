from pydantic import BaseModel, Field

from jarvis_contracts import LoginRequest, LoginResponse

# re-export for backwards compatibility within gateway
__all__ = ["LoginRequest", "LoginResponse"]


class TokenValidationResponse(BaseModel):
    user_id: str
    tenant_id: str
    role: str
    active: bool = True


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=1)


class TenantResponse(BaseModel):
    id: str
    name: str
    created_at: str


class UserCreateRequest(BaseModel):
    tenant_id: str
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    role: str = "member"


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    username: str
    role: str
    created_at: str


class SessionCreateRequest(BaseModel):
    title: str = Field(default="new session")


class SessionResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    title: str
    status: str
    created_at: str
    updated_at: str


class SessionTerminateResponse(BaseModel):
    id: str
    status: str
    updated_at: str


class AuditLogItem(BaseModel):
    id: int
    action: str
    resource: str
    status: str
    detail: str
    request_id: str
    actor_user_id: str
    tenant_id: str
    created_at: str
