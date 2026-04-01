import logging

from fastapi import FastAPI

from middleware.core_client import CoreClient
from middleware.auth_middleware import GatewayAuthMiddleware
from middleware.gateway_client import GatewayClient
from router.router import api_router

logging.basicConfig(level=logging.INFO)


API_DESCRIPTION = """
JARVIS controller public API.

This service is the orchestration layer in front of gateway/core services and exposes
conversation, auth, execution, and model-configuration endpoints.

Authentication:
- Public endpoints: `/health`, `/auth/login`, `/docs`, `/redoc`, `/openapi.json`
- Protected endpoints: send `Authorization: Bearer <token>`
- Optional tracing header: `x-request-id`
- Optional client header: `x-client-id`
""".strip()

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Service liveness endpoint.",
    },
    {
        "name": "auth",
        "description": "Authentication and current principal endpoints.",
    },
    {
        "name": "conversation",
        "description": "Conversation orchestration endpoints.",
    },
    {
        "name": "chat",
        "description": "Direct chat and model configuration endpoints.",
    },
    {
        "name": "execution",
        "description": "Mock execution and verification endpoints.",
    },
]


def create_app(
    gateway_client: GatewayClient | None = None,
    core_client: CoreClient | None = None,
) -> FastAPI:
    app = FastAPI(
        title="JARVIS Controller API",
        description=API_DESCRIPTION,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=OPENAPI_TAGS,
    )
    app.state.gateway_client = gateway_client or GatewayClient()
    app.state.core_client = core_client or CoreClient()
    app.add_middleware(GatewayAuthMiddleware, gateway_client=app.state.gateway_client)
    app.include_router(api_router)
    return app


app = create_app()
