"""Logging helpers and error responses."""

from __future__ import annotations

import contextvars
import json
import logging
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from tenacity import RetryError

from app.core.config import Settings, settings
from app.core.exceptions import ClinicBlockedError
from app.llm.client import LLMUnavailable

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
CHAT_LOGGER_NAME = "chat_run"
_chat_log_path: Path | None = None


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
    _configure_chat_file_logger()


def _clear_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def _configure_chat_file_logger() -> None:
    global _chat_log_path
    logger = logging.getLogger(CHAT_LOGGER_NAME)
    _clear_handlers(logger)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if chat_file_logs_enabled(settings):
        try:
            log_dir = Path(settings.chat_log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = log_dir / f"chat_run_{timestamp}.log"

            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(file_handler)
            _chat_log_path = log_path
            return
        except OSError:
            logging.getLogger(__name__).exception(
                "failed to configure chat file logging, falling back to stdout"
            )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream_handler)
    _chat_log_path = None


def chat_log_path() -> Path | None:
    return _chat_log_path


def chat_file_logs_enabled(settings_obj: Settings) -> bool:
    if settings_obj.is_serverless:
        return False
    if settings_obj.chat_file_logs is not None:
        return settings_obj.chat_file_logs
    return settings_obj.env != "prod"


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}…"


def _sanitize_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ("password", "token", "authorization", "jwt"))


def _redact_string(value: str) -> str:
    patterns = [
        r"(password)\s*[:=]\s*[^\s]+",
        r"(token)\s*[:=]\s*[^\s]+",
        r"(authorization)\s*[:=]\s*[^\s]+",
        r"(jwt)\s*[:=]\s*[^\s]+",
        r"(access_token)\s*[:=]\s*[^\s]+",
    ]
    redacted = value
    for pattern in patterns:
        redacted = re.sub(pattern, r"\\1=[redacted]", redacted, flags=re.IGNORECASE)
    return redacted


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, val in value.items():
            if _sanitize_key(str(key)):
                sanitized[key] = "[redacted]"
            else:
                sanitized[key] = _sanitize(val)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _truncate(_redact_string(value), settings.max_context_chars)
    return value


def log_chat_event(event: str, payload: dict[str, Any]) -> None:
    logger = logging.getLogger(CHAT_LOGGER_NAME)
    sanitized = _sanitize(payload)
    record = {
        "event": event,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **sanitized,
    }
    line = json.dumps(record, default=str)
    if logger.handlers and logger.isEnabledFor(logging.INFO):
        logger.info(line)
        for handler in logger.handlers:
            if hasattr(handler, "flush"):
                handler.flush()
        return
    if _chat_log_path is None:
        return
    with _chat_log_path.open("a", encoding="utf-8", errors="ignore") as handle:
        handle.write(f"{line}\n")


def error_payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
        }
    }


def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request.state.error_code = "VALIDATION_ERROR"
    return JSONResponse(
        status_code=422,
        content=error_payload(
            code="VALIDATION_ERROR",
            message="Validation error",
            details=exc.errors(),
        ),
    )


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    details: dict[str, Any] = {}
    if exc.detail is not None:
        details = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
    request.state.error_code = f"HTTP_{exc.status_code}"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code=f"HTTP_{exc.status_code}",
            message="HTTP error",
            details=details,
        ),
    )


def clinic_blocked_handler(request: Request, exc: ClinicBlockedError) -> JSONResponse:
    request.state.error_code = "CLINIC_BLOCKED"
    return JSONResponse(
        status_code=403,
        content=error_payload(
            code="CLINIC_BLOCKED",
            message="Clinic is blocked",
            details={"clinic_id": exc.clinic_id},
        ),
    )


def llm_unavailable_handler(request: Request, exc: LLMUnavailable) -> JSONResponse:
    request.state.error_code = "LLM_UNAVAILABLE"
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


def retry_error_handler(request: Request, exc: RetryError) -> JSONResponse:
    request.state.error_code = "LLM_UNAVAILABLE"
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


def db_timeout_handler(request: Request, exc: SQLAlchemyTimeoutError) -> JSONResponse:
    request.state.error_code = "DB_UNAVAILABLE"
    details: dict[str, Any] = {}
    if settings.env in {"dev", "test"}:
        details["error"] = str(exc)
    return JSONResponse(
        status_code=503,
        content=error_payload(
            code="DB_UNAVAILABLE",
            message="Database unavailable",
            details=details,
        ),
    )


def unhandled_exception_handler(
    request: Request, exc: Exception, settings: Settings
) -> JSONResponse:
    request.state.error_code = "INTERNAL_SERVER_ERROR"
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
