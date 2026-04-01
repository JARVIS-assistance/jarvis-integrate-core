from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import uuid4

from fastapi import HTTPException, status
from jarvis_contracts import ErrorResponse
from starlette.websockets import WebSocket

from ai import AIService
from core.db.db_connection import DBClient
from core.db.db_operations import (
    add_message,
    create_user_model_config,
    get_active_model_for_user,
    get_model_config_by_id_for_user,
    get_or_create_session_for_user,
    get_user_ai_selection,
    list_user_model_configs,
    set_user_ai_selection,
)
from router import choose_route
from safety import safety_gate

from .schemas import (
    ChatOnceRequest,
    ModelConfigUpsertRequest,
    ModelSelectionUpsertRequest,
)


class ChatService:
    def __init__(self, db: DBClient, ai_service: AIService) -> None:
        self.db = db
        self.ai_service = ai_service

    def _fallback_model_config(self) -> dict[str, str | bool | None]:
        return {
            "id": "default-local",
            "provider_mode": "local",
            "provider_name": "local-default",
            "model_name": "local-stub",
            "api_key": None,
            "endpoint": None,
            "is_active": True,
            "is_default": True,
            "supports_stream": True,
            "supports_realtime": False,
            "transport": "http_sse",
            "input_modalities": "text",
            "output_modalities": "text",
        }

    def _select_model_config(
        self, user_id: str, purpose: str
    ) -> dict[str, str | bool | None]:
        selected_id: str | None = None
        selection = get_user_ai_selection(self.db, user_id=user_id)
        if selection is not None:
            if purpose == "deep":
                selected_id = selection.get("deep_model_config_id")
            else:
                selected_id = selection.get("realtime_model_config_id")

        if selected_id:
            selected_model = get_model_config_by_id_for_user(
                self.db, user_id=user_id, model_config_id=selected_id
            )
            if selected_model is not None and bool(
                selected_model.get("is_active", True)
            ):
                return selected_model

        config = get_active_model_for_user(self.db, user_id=user_id)
        return config or {
            **self._fallback_model_config(),
        }

    async def request_once(
        self, body: ChatOnceRequest, request_id: str, user_id: str, email: str
    ) -> dict[str, str] | ErrorResponse:
        allowed, reason = safety_gate(body.message, body.confirm)
        if not allowed:
            return ErrorResponse(
                error_code="SAFETY_BLOCKED",
                message=reason or "blocked",
                request_id=request_id,
            )

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing user id in auth token",
            )

        session = get_or_create_session_for_user(
            self.db, user_id=user_id, email=email or "unknown@local.jarvis"
        )
        session_id = session["id"]
        route = choose_route(body.message, body.task_type)
        add_message(self.db, session_id, "user", body.message)

        purpose = "deep" if route == "deep" else "realtime"
        selected = self._select_model_config(user_id=user_id, purpose=purpose)
        ai_result = await self.ai_service.respond_once(
            {
                "message": body.message,
                "route": route,
                "request_id": request_id,
                "provider_mode": selected["provider_mode"],
                "provider_name": selected["provider_name"],
                "model_name": selected["model_name"],
                "api_key": selected.get("api_key"),
                "endpoint": selected.get("endpoint"),
            }
        )
        add_message(self.db, session_id, "assistant", ai_result["content"])
        return {
            "request_id": request_id,
            "route": route,
            "provider_mode": ai_result["provider_mode"],
            "provider_name": ai_result["provider_name"],
            "model_name": ai_result["model_name"],
            "content": ai_result["content"],
        }

    # ── realtime 함수에서 쓸 함수들 ───────────────────────────────────────────

    @staticmethod
    def _parse_ws_event(raw: str) -> dict | None:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    @staticmethod
    async def _cancel_task(task: asyncio.Task[None] | None) -> None:
        """Cancel an asyncio task and suppress CancelledError."""
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _interrupt_generation(
        self,
        websocket: WebSocket,
        generation: asyncio.Task[None] | None,
        rt_session_id: str | None,
        request_payload: dict[str, str | None] | None,
        reason: str,
    ) -> None:
        """Cancel the active generation task and notify the client."""
        await self._cancel_task(generation)
        if rt_session_id and request_payload:
            await self.ai_service.cancel_generation(request_payload, rt_session_id)
        payload: dict[str, str] = {"type": "interrupted", "content": reason}
        if request_payload:
            rid = request_payload.get("request_id")
            if rid:
                payload["request_id"] = str(rid)
        await websocket.send_json(payload)

    async def _stream_generation(
        self,
        websocket: WebSocket,
        request_payload: dict[str, str | None],
        rt_session_id: str,
        request_id: str,
        chat_session_id: str,
    ) -> None:
        """Stream tokens from the AI service to the WebSocket client."""
        chunks: list[str] = []
        try:
            async for token in self.ai_service.realtime_session_send(
                request_payload, rt_session_id
            ):
                chunks.append(token)
                await websocket.send_json(
                    {
                        "type": "assistant_delta",
                        "request_id": request_id,
                        "content": token,
                    }
                )
        except asyncio.CancelledError:
            return
        except Exception:
            await websocket.send_json(
                {
                    "type": "error",
                    "request_id": request_id,
                    "content": "generation failed",
                }
            )
            return

        full = "".join(chunks).strip()
        if full:
            add_message(self.db, chat_session_id, "assistant", full)
        await websocket.send_json({"type": "assistant_done", "request_id": request_id})

    # ── run_realtime ────────────────────────────────────────────

    async def run_realtime(
        self, websocket: WebSocket, user_id: str, email: str
    ) -> None:
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing user id in auth token",
            )

        await websocket.accept()
        await websocket.send_json({"type": "ready"})

        session = get_or_create_session_for_user(
            self.db, user_id=user_id, email=email or "unknown@local.jarvis"
        )
        chat_session_id = session["id"]
        active_generation: asyncio.Task[None] | None = None
        active_rt_session_id: str | None = None
        active_request: dict[str, str | None] | None = None
        realtime_session_request: dict[str, str | None] | None = None

        try:
            while True:
                raw = await websocket.receive_text()
                event = self._parse_ws_event(raw)
                if event is None:
                    await websocket.send_json(
                        {"type": "error", "content": "invalid json"}
                    )
                    continue

                event_type = str(event.get("type", ""))
                if event_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                if event_type == "interrupt":
                    await self._interrupt_generation(
                        websocket,
                        active_generation,
                        active_rt_session_id,
                        active_request,
                        reason="user_interrupt",
                    )
                    active_generation = None
                    continue

                if event_type != "user_message":
                    await websocket.send_json(
                        {"type": "error", "content": "unsupported event type"}
                    )
                    continue

                # Barge-in: new message interrupts in-flight generation
                if active_generation is not None and not active_generation.done():
                    await self._interrupt_generation(
                        websocket,
                        active_generation,
                        active_rt_session_id,
                        active_request,
                        reason="barge_in",
                    )
                    active_generation = None

                content = str(event.get("content", "")).strip()
                task_type = str(event.get("task_type", "general"))
                confirm = bool(event.get("confirm", False))
                if not content:
                    await websocket.send_json(
                        {"type": "error", "content": "empty content"}
                    )
                    continue

                allowed, reason = safety_gate(content, confirm)
                if not allowed:
                    await websocket.send_json(
                        {"type": "error", "content": reason or "blocked"}
                    )
                    continue

                selected = self._select_model_config(
                    user_id=user_id, purpose="realtime"
                )
                if not bool(selected.get("supports_realtime", False)):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "content": "selected model does not support realtime",
                        }
                    )
                    continue

                route = choose_route(content, task_type)
                request_id = str(uuid4())
                add_message(self.db, chat_session_id, "user", content)
                request_payload: dict[str, str | None] = {
                    "message": content,
                    "route": route,
                    "request_id": request_id,
                    "provider_mode": str(selected["provider_mode"]),
                    "provider_name": str(selected["provider_name"]),
                    "model_name": str(selected["model_name"]),
                    "api_key": selected.get("api_key"),
                    "endpoint": selected.get("endpoint"),
                }
                active_request = request_payload

                if active_rt_session_id is None:
                    active_rt_session_id = await self.ai_service.realtime_session_start(
                        request_payload
                    )
                    realtime_session_request = request_payload

                await websocket.send_json(
                    {
                        "type": "meta",
                        "request_id": request_id,
                        "route": route,
                        "provider_mode": selected["provider_mode"],
                        "provider_name": selected["provider_name"],
                        "model_name": selected["model_name"],
                        "session_id": active_rt_session_id,
                    }
                )

                active_generation = asyncio.create_task(
                    self._stream_generation(
                        websocket,
                        request_payload,
                        active_rt_session_id or "",
                        request_id,
                        chat_session_id,
                    )
                )
        finally:
            await self._cancel_task(active_generation)
            if active_rt_session_id and realtime_session_request:
                await self.ai_service.realtime_session_close(
                    realtime_session_request, active_rt_session_id
                )

    async def run_realtime_sse(
        self,
        message: str,
        task_type: str,
        confirm: bool,
        request_id: str,
        user_id: str,
        email: str,
    ) -> AsyncGenerator[str, None]:
        """SSE 스트리밍: AI 제공자에서 토큰을 받아 SSE 이벤트로 yield."""
        if not user_id:
            yield f"event: error\ndata: {json.dumps({'content': 'missing user id'})}\n\n"
            return

        allowed, reason = safety_gate(message, confirm)
        if not allowed:
            yield f"event: error\ndata: {json.dumps({'content': reason or 'blocked'})}\n\n"
            return

        session = get_or_create_session_for_user(
            self.db, user_id=user_id, email=email or "unknown@local.jarvis"
        )
        session_id = session["id"]
        route = choose_route(message, task_type)
        add_message(self.db, session_id, "user", message)

        purpose = "deep" if route == "deep" else "realtime"
        selected = self._select_model_config(user_id=user_id, purpose=purpose)

        if not bool(selected.get("supports_stream", False)):
            yield f"event: error\ndata: {json.dumps({'content': 'selected model does not support streaming'})}\n\n"
            return

        request_payload = {
            "message": message,
            "route": route,
            "request_id": request_id,
            "provider_mode": str(selected["provider_mode"]),
            "provider_name": str(selected["provider_name"]),
            "model_name": str(selected["model_name"]),
            "api_key": selected.get("api_key"),
            "endpoint": selected.get("endpoint"),
        }

        # meta event
        meta = {
            "type": "meta",
            "request_id": request_id,
            "route": route,
            "provider_mode": selected["provider_mode"],
            "provider_name": selected["provider_name"],
            "model_name": selected["model_name"],
        }
        yield f"event: meta\ndata: {json.dumps(meta)}\n\n"

        # stream tokens
        chunks: list[str] = []
        try:
            async for token in self.ai_service.stream_tokens(request_payload):
                chunks.append(token)
                yield f"event: assistant_delta\ndata: {json.dumps({'request_id': request_id, 'content': token})}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'request_id': request_id, 'content': str(exc)})}\n\n"
            return

        full = "".join(chunks).strip()
        if full:
            add_message(self.db, session_id, "assistant", full)

        yield f"event: assistant_done\ndata: {json.dumps({'request_id': request_id, 'content': full})}\n\n"

    async def close_realtime_session(
        self, request: dict[str, str | None], realtime_session_id: str
    ) -> None:
        await self.ai_service.realtime_session_close(request, realtime_session_id)

    def create_model_config(
        self, user_id: str, body: ModelConfigUpsertRequest
    ) -> dict[str, str | bool | None]:
        return create_user_model_config(
            self.db,
            user_id=user_id,
            provider_mode=body.provider_mode,
            provider_name=body.provider_name,
            model_name=body.model_name,
            api_key=body.api_key,
            endpoint=body.endpoint,
            is_default=body.is_default,
            supports_stream=body.supports_stream,
            supports_realtime=body.supports_realtime,
            transport=body.transport,
            input_modalities=body.input_modalities,
            output_modalities=body.output_modalities,
        )

    def list_model_configs(self, user_id: str) -> list[dict[str, str | bool | None]]:
        return list_user_model_configs(self.db, user_id=user_id)

    def set_model_selection(
        self, user_id: str, body: ModelSelectionUpsertRequest
    ) -> dict[str, str | None]:
        if body.realtime_model_config_id is not None:
            realtime = get_model_config_by_id_for_user(
                self.db, user_id=user_id, model_config_id=body.realtime_model_config_id
            )
            if realtime is None:
                raise HTTPException(
                    status_code=400, detail="invalid realtime_model_config_id"
                )
        if body.deep_model_config_id is not None:
            deep = get_model_config_by_id_for_user(
                self.db, user_id=user_id, model_config_id=body.deep_model_config_id
            )
            if deep is None:
                raise HTTPException(
                    status_code=400, detail="invalid deep_model_config_id"
                )

        return set_user_ai_selection(
            self.db,
            user_id=user_id,
            realtime_model_config_id=body.realtime_model_config_id,
            deep_model_config_id=body.deep_model_config_id,
        )

    def get_model_selection(self, user_id: str) -> dict[str, str | None]:
        selection = get_user_ai_selection(self.db, user_id=user_id)
        if selection is not None:
            return selection
        return {
            "realtime_model_config_id": None,
            "deep_model_config_id": None,
        }
