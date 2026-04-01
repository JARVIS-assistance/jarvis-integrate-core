from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


CONTRACT_VERSION = "1.0"


class ConversationMode(StrEnum):
    REALTIME = "realtime"
    DEEP = "deep"
    PLANNING = "planning"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    contract_version: str = Field(default=CONTRACT_VERSION)
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    role: str


class PrincipalResponse(BaseModel):
    contract_version: str = Field(default=CONTRACT_VERSION)
    user_id: str
    tenant_id: str
    role: str
    active: bool = True


class ConversationRequest(BaseModel):
    message: str = Field(..., min_length=1)
    override: ConversationMode | None = None
    recent_failures: int = 0
    ambiguity_count: int = 0
    turn_index: int = 0


class InternalConversationRequest(BaseModel):
    mode: Literal["realtime", "deep"]
    message: str = Field(..., min_length=1)


class PlanStepPayload(BaseModel):
    id: str
    title: str
    description: str
    status: str


class PlanningPayload(BaseModel):
    goal: str
    constraints: list[str]
    steps: list[PlanStepPayload]
    exit_condition: str
    notes: list[str]


class ConversationResponse(BaseModel):
    contract_version: str = Field(default=CONTRACT_VERSION)
    mode: ConversationMode
    triggered: bool
    confidence: float
    reasons: list[str]
    handler: str
    content: str | None = None
    summary: str | None = None
    next_actions: list[str] = Field(default_factory=list)
    planning: PlanningPayload | None = None


class InternalConversationResponse(BaseModel):
    mode: Literal["realtime", "deep"]
    summary: str
    content: str
    next_actions: list[str] = Field(default_factory=list)
