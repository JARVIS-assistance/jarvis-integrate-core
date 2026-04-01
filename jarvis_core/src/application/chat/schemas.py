from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatOnceRequest(BaseModel):
    message: str = Field(min_length=1)
    task_type: Literal["general", "analysis", "execution"] = "general"
    confirm: bool = False


class ChatOnceResponse(BaseModel):
    request_id: str
    route: str
    provider_mode: Literal["token", "local"]
    provider_name: str
    model_name: str
    content: str


class ModelConfigUpsertRequest(BaseModel):
    provider_mode: Literal["token", "local"]
    provider_name: str = Field(min_length=1, max_length=60)
    model_name: str = Field(min_length=1, max_length=120)
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    is_default: bool = False
    supports_stream: bool = True
    supports_realtime: bool = False
    transport: Literal["http_sse", "websocket"] = "http_sse"
    input_modalities: str = "text"
    output_modalities: str = "text"


class ModelConfigResponse(BaseModel):
    id: str
    provider_mode: Literal["token", "local"]
    provider_name: str
    model_name: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    supports_stream: bool = True
    supports_realtime: bool = False
    transport: Literal["http_sse", "websocket"] = "http_sse"
    input_modalities: str = "text"
    output_modalities: str = "text"


class ModelSelectionUpsertRequest(BaseModel):
    realtime_model_config_id: str | None = None
    deep_model_config_id: str | None = None


class ModelSelectionResponse(BaseModel):
    realtime_model_config_id: str | None = None
    deep_model_config_id: str | None = None
