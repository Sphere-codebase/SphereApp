"""Request logging with latency and request_id."""

from __future__ import annotations

import logging
import time

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
                self.logger.info(
                    "request completed status=%s path=%s latency_ms=%.2f",
                    message.get("status"),
                    scope.get("path"),
                    latency_ms,
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)
