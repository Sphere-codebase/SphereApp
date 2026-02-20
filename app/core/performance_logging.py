"""Performance logging helpers for request and SQL timings."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Awaitable, Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from fastapi import Request, Response
from sqlalchemy import Engine, event

from app.core.config import settings
from app.core.logging import request_id_ctx

# Thresholds for slow logging. Adjust here if needed.
# - Requests slower than SLOW_REQUEST_MS will be logged at WARNING.
# - SQL queries slower than SLOW_QUERY_MS will be logged at INFO.
SLOW_REQUEST_MS = 1000.0
SLOW_QUERY_MS = 200.0

PERFORMANCE_LOGGER_NAME = "performance"
PERFORMANCE_LOG_FILE = "performance.log"
_performance_configured = False
_request_metrics_lock = threading.Lock()
_sql_count_by_request: dict[str, int] = {}
_connect_created_by_request: dict[str, bool] = {}


class _PerformanceDefaultsFilter(logging.Filter):
    """Ensure required log fields exist for the performance formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "path"):
            record.path = "-"
        if not hasattr(record, "method"):
            record.method = "-"
        if not hasattr(record, "status_code"):
            record.status_code = "-"
        if not hasattr(record, "duration_ms"):
            record.duration_ms = "-"
        if not hasattr(record, "sql_count"):
            record.sql_count = "-"
        if not hasattr(record, "connect_created"):
            record.connect_created = "-"
        return True


def configure_performance_logging() -> logging.Logger:
    """Configure file-based structured logging for performance metrics."""
    global _performance_configured
    logger = logging.getLogger(PERFORMANCE_LOGGER_NAME)
    if _performance_configured:
        return logger

    # Performance logs are written to logs/performance.log by default.
    log_dir = Path(settings.chat_log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / PERFORMANCE_LOG_FILE

    handler_exists = False
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == log_path:
            handler_exists = True
            break

    if not handler_exists:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        handler.setLevel(logging.INFO)
        handler.addFilter(_PerformanceDefaultsFilter())
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s "
                "path=%(path)s method=%(method)s status=%(status_code)s "
                "duration_ms=%(duration_ms)s sql_count=%(sql_count)s "
                "connect_created=%(connect_created)s %(message)s"
            )
        )
        logger.addHandler(handler)

    logger.setLevel(logging.INFO)
    logger.propagate = False
    _performance_configured = True
    return logger


def _current_request_id() -> str:
    try:
        request_id = request_id_ctx.get()
    except Exception:
        request_id = "-"
    return request_id or "-"


def _increment_sql_count() -> None:
    request_id = _current_request_id()
    if request_id == "-":
        return
    with _request_metrics_lock:
        _sql_count_by_request[request_id] = _sql_count_by_request.get(request_id, 0) + 1


def _mark_connect_created() -> None:
    request_id = _current_request_id()
    if request_id == "-":
        return
    with _request_metrics_lock:
        _connect_created_by_request[request_id] = True


def _pop_request_metrics(request_id: str) -> tuple[int, bool]:
    if request_id == "-":
        return 0, False
    with _request_metrics_lock:
        sql_count = _sql_count_by_request.pop(request_id, 0)
        connect_created = _connect_created_by_request.pop(request_id, False)
    return sql_count, connect_created


async def performance_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Middleware to log per-request duration and flag slow endpoints.

    Look for WARNING entries in performance.log to identify slow requests.
    """
    logger = configure_performance_logging()
    start = time.perf_counter()
    status_code: int | str = "-"
    request_id = (
        (request.scope.get("state") or {}).get("request_id")  # type: ignore[assignment]
        or _current_request_id()
    )
    if request_id != "-":
        # Defensive cleanup in case callers reuse X-Request-ID values.
        _pop_request_metrics(request_id)
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception:
        status_code = 500
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000.0
        request_id = (
            (request.scope.get("state") or {}).get("request_id")  # type: ignore[assignment]
            or _current_request_id()
        )
        sql_count, connect_created = _pop_request_metrics(request_id)
        level = logging.WARNING if duration_ms > SLOW_REQUEST_MS else logging.INFO
        logger.log(
            level,
            f"request completed request_id={request_id} "
            f"sql_count={sql_count} connect_created={connect_created}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": status_code,
                "duration_ms": f"{duration_ms:.2f}",
                "sql_count": str(sql_count),
                "connect_created": str(connect_created).lower(),
            },
        )


def setup_sqlalchemy_query_logging(engine: Engine) -> None:
    """Attach SQLAlchemy event listeners to log slow query execution times."""
    if getattr(engine, "_performance_query_logging_installed", False):
        return

    engine._performance_query_logging_installed = True
    logger = configure_performance_logging()

    @event.listens_for(engine, "do_connect")
    def _do_connect(dialect, conn_rec, cargs, cparams):
        start = time.perf_counter()
        dbapi_conn = dialect.connect(*cargs, **cparams)
        conn_rec.info["connect_duration_ms"] = (time.perf_counter() - start) * 1000.0
        return dbapi_conn

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, conn_rec) -> None:
        duration_ms = conn_rec.info.pop("connect_duration_ms", None)
        duration_label = f"{duration_ms:.2f}" if duration_ms is not None else "-"
        _mark_connect_created()
        logger.info(
            f"db connect request_id={_current_request_id()}",
            extra={
                "path": "db",
                "method": "CONNECT",
                "status_code": "-",
                "duration_ms": duration_label,
            },
        )

    @event.listens_for(engine, "checkout")
    def _on_checkout(dbapi_conn, conn_rec, conn_proxy) -> None:
        logger.info(
            f"db checkout request_id={_current_request_id()}",
            extra={
                "path": "db",
                "method": "CHECKOUT",
                "status_code": "-",
                "duration_ms": "-",
            },
        )

    @event.listens_for(engine, "checkin")
    def _on_checkin(dbapi_conn, conn_rec) -> None:
        logger.info(
            f"db checkin request_id={_current_request_id()}",
            extra={
                "path": "db",
                "method": "CHECKIN",
                "status_code": "-",
                "duration_ms": "-",
            },
        )

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn,
        cursor,
        statement: str,
        parameters: Any,
        context,
        executemany: bool,
    ) -> None:
        conn.info["query_start_time"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn,
        cursor,
        statement: str,
        parameters: Any,
        context,
        executemany: bool,
    ) -> None:
        start = conn.info.pop("query_start_time", None)
        if start is None:
            return
        _increment_sql_count()
        duration_ms = (time.perf_counter() - start) * 1000.0
        if duration_ms < SLOW_QUERY_MS:
            return
        trimmed = " ".join(statement.split())
        if len(trimmed) > 500:
            trimmed = f"{trimmed[:500]}..."
        logger.info(
            f"slow sql request_id={_current_request_id()} sql={trimmed}",
            extra={
                "path": "db",
                "method": "SQL",
                "status_code": "-",
                "duration_ms": f"{duration_ms:.2f}",
            },
        )
