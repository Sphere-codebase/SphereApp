"""FastAPI application entrypoint.

Codex: implement the app wiring, include routers, middleware, and dependencies.
"""

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from tenacity import RetryError

from app.api.routes import auth_router, chat_router, health_router
from app.core.config import settings
from app.core.logging import (
    configure_logging,
    http_exception_handler,
    llm_unavailable_handler,
    retry_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.llm.client import LLMUnavailable
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware

configure_logging(settings.log_level)

app = FastAPI(title="claims-assistant")
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,  # type: ignore[arg-type]
)
app.add_exception_handler(LLMUnavailable, llm_unavailable_handler)  # type: ignore[arg-type]
app.add_exception_handler(RetryError, retry_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(
    Exception, lambda request, exc: unhandled_exception_handler(request, exc, settings)
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(health_router)

# TODO: include routers:
# - health
# - auth
# - chat
