"""FastAPI application entrypoint.

Codex: implement the app wiring, include routers, middleware, and dependencies.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from tenacity import RetryError

from app.api.routes import (
    admin_router,
    auth_router,
    chat_router,
    chat_sessions_router,
    frontend_log_router,
    health_router,
    ui_router,
)
from app.core.config import settings
from app.core.logging import (
    configure_logging,
    db_timeout_handler,
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

ROOT_DIR = Path(__file__).resolve().parents[1]
app = FastAPI(title="claims-assistant")
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "static")), name="static")
app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,  # type: ignore[arg-type]
)
app.add_exception_handler(LLMUnavailable, llm_unavailable_handler)  # type: ignore[arg-type]
app.add_exception_handler(RetryError, retry_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(SQLAlchemyTimeoutError, db_timeout_handler)  # type: ignore[arg-type]
app.add_exception_handler(
    Exception, lambda request, exc: unhandled_exception_handler(request, exc, settings)
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(chat_router)
app.include_router(chat_sessions_router)
app.include_router(frontend_log_router)
app.include_router(health_router)
app.include_router(ui_router)

# TODO: include routers:
# - health
# - auth
# - chat
