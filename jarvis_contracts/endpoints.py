from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EndpointSpec:
    service: str
    name: str
    method: str
    path: str
    internal: bool = False

    def url(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}{self.path}"


class JarvisCoreEndpoints:
    HEALTH = EndpointSpec(
        service="jarvis-core",
        name="health",
        method="GET",
        path="/health",
    )
    INTERNAL_CONVERSATION_RESPOND = EndpointSpec(
        service="jarvis-core",
        name="internal_conversation_respond",
        method="POST",
        path="/internal/conversation/respond",
        internal=True,
    )

    INTERNAL_CHAT_REQUEST = EndpointSpec(
        service="jarvis-core",
        name="internal_chat_request",
        method="POST",
        path="/internal/chat/request",
        internal=True,
    )
    INTERNAL_CHAT_STREAM = EndpointSpec(
        service="jarvis-core",
        name="internal_chat_stream",
        method="POST",
        path="/internal/chat/stream",
        internal=True,
    )
    INTERNAL_CHAT_MODEL_CONFIG = EndpointSpec(
        service="jarvis-core",
        name="internal_chat_model_config",
        method="POST",
        path="/internal/chat/model-config",
        internal=True,
    )
    INTERNAL_CHAT_MODEL_CONFIG_LIST = EndpointSpec(
        service="jarvis-core",
        name="internal_chat_model_config_list",
        method="GET",
        path="/internal/chat/model-config",
        internal=True,
    )
    INTERNAL_CHAT_MODEL_SELECTION = EndpointSpec(
        service="jarvis-core",
        name="internal_chat_model_selection",
        method="POST",
        path="/internal/chat/model-selection",
        internal=True,
    )
    INTERNAL_CHAT_MODEL_SELECTION_GET = EndpointSpec(
        service="jarvis-core",
        name="internal_chat_model_selection_get",
        method="GET",
        path="/internal/chat/model-selection",
        internal=True,
    )

    @classmethod
    def all(cls) -> tuple[EndpointSpec, ...]:
        return (
            cls.HEALTH,
            cls.INTERNAL_CONVERSATION_RESPOND,
            cls.INTERNAL_CHAT_REQUEST,
            cls.INTERNAL_CHAT_STREAM,
            cls.INTERNAL_CHAT_MODEL_CONFIG,
            cls.INTERNAL_CHAT_MODEL_CONFIG_LIST,
            cls.INTERNAL_CHAT_MODEL_SELECTION,
            cls.INTERNAL_CHAT_MODEL_SELECTION_GET,
        )

    @classmethod
    def for_controller(cls) -> tuple[EndpointSpec, ...]:
        return tuple(endpoint for endpoint in cls.all() if endpoint.internal)


class JarvisGatewayEndpoints:
    HEALTH = EndpointSpec(
        service="jarvis-gateway",
        name="health",
        method="GET",
        path="/health",
    )
    LOGIN = EndpointSpec(
        service="jarvis-gateway",
        name="login",
        method="POST",
        path="/auth/login",
    )
    LOGOUT = EndpointSpec(
        service="jarvis-gateway",
        name="logout",
        method="POST",
        path="/auth/logout",
    )
    VALIDATE = EndpointSpec(
        service="jarvis-gateway",
        name="validate",
        method="GET",
        path="/auth/validate",
    )

    @classmethod
    def all(cls) -> tuple[EndpointSpec, ...]:
        return (
            cls.HEALTH,
            cls.LOGIN,
            cls.LOGOUT,
            cls.VALIDATE,
        )
