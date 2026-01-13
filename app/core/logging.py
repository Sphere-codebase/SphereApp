"""Logging helpers and error responses."""

from __future__ import annotations

import contextvars
import logging
import traceback
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from tenacity import RetryError

from app.core.config import Settings, settings
from app.llm.client import LLMUnavailable

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Always attach request_id from contextvar for correlation.
        rid = request_id_ctx.get()
        record.request_id = rid if rid else "-"
        return True


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s %(name)s request_id=%(request_id)s %(message)s",
    )
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(RequestIdFilter())


def error_payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
        }
    }


def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(
            code="VALIDATION_ERROR",
            message="Validation error",
            details=exc.errors(),
        ),
    )


def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    details: dict[str, Any] = {}
    if exc.detail is not None:
        details = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code=f"HTTP_{exc.status_code}",
            message="HTTP error",
            details=details,
        ),
    )


def llm_unavailable_handler(_: Request, exc: LLMUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=error_payload(
            code="LLM_UNAVAILABLE",
            message="LLM service is unavailable",
            details={
                "error": str(exc),
                "base_url": settings.lmstudio_base_url,
                "timeout_seconds": settings.llm_timeout_seconds,
            },
        ),
    )


def retry_error_handler(_: Request, exc: RetryError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=error_payload(
            code="LLM_UNAVAILABLE",
            message="LLM service is unavailable",
            details={
                "error": str(exc),
                "base_url": settings.lmstudio_base_url,
                "timeout_seconds": settings.llm_timeout_seconds,
            },
        ),
    )


def unhandled_exception_handler(_: Request, exc: Exception, settings: Settings) -> JSONResponse:
    logger = logging.getLogger(__name__)
    logger.error("unhandled exception", exc_info=exc)
    details: dict[str, Any] = {}
    if settings.env in {"dev", "test"}:
        details["traceback"] = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content=error_payload(
            code="INTERNAL_SERVER_ERROR",
            message="Internal server error",
            details=details,
        ),
    )
