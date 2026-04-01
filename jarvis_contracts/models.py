from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


CONTRACT_VERSION = "1.0"


class PlanStep(BaseModel):
    id: str = Field(..., description="Step identifier")
    action: str = Field(..., description="Planned action description")
    reasoning: str = Field(..., description="Why this step is needed")


class PlanRequest(BaseModel):
    contract_version: str = Field(default=CONTRACT_VERSION)
    session_id: str
    user_input: str
    task_type: Literal["general", "analysis", "execution"] = "general"


class ExecuteRequest(BaseModel):
    contract_version: str = Field(default=CONTRACT_VERSION)
    request_id: str
    action: str
    target: str
    value: Optional[str] = None


class ExecuteResult(BaseModel):
    contract_version: str = Field(default=CONTRACT_VERSION)
    request_id: str
    success: bool
    action: str
    detail: str
    output: dict[str, Any] = Field(default_factory=dict)


class VerifyRequest(BaseModel):
    contract_version: str = Field(default=CONTRACT_VERSION)
    request_id: str
    check: str
    expected: str
    actual: str


class VerifyResult(BaseModel):
    contract_version: str = Field(default=CONTRACT_VERSION)
    request_id: str
    passed: bool
    detail: str


class ErrorResponse(BaseModel):
    contract_version: str = Field(default=CONTRACT_VERSION)
    error_code: str
    message: str
    request_id: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)
