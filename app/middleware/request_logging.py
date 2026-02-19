"""Request logging with latency and request_id."""

from __future__ import annotations

import json
import logging
import time

from app.core.logging import request_id_ctx

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger(__name__)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                latency_ms = (time.monotonic() - start) * 1000
                state = scope.get("state") or {}
                record = {
                    "event": "http_request",
                    "request_id": state.get("request_id") or request_id_ctx.get(),
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": message.get("status"),
                    "duration_ms": round(latency_ms, 2),
                    "user_id": state.get("current_user_id"),
                    "clinic_id": state.get("current_user_clinic_id"),
                    "role": state.get("current_user_role"),
                    "error_code": state.get("error_code"),
                }
                self.logger.info(json.dumps(record, default=str))
            await send(message)

        await self.app(scope, receive, send_wrapper)
