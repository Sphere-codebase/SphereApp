"""Database session utilities."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from typing import Literal

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import request_id_ctx
from app.core.tenancy import (
    clear_rls_state,
    get_current_clinic_id,
    get_current_is_platform_admin,
    mark_rls_state,
)

logger = logging.getLogger(__name__)
_session_count_lock = threading.Lock()
_request_session_counts: dict[str, int] = {}


def _is_sqlite(url: str) -> bool:
    return url.lower().startswith("sqlite")


def _is_psycopg_postgres(url: str) -> bool:
    return url.lower().startswith("postgresql+psycopg://")


def _uses_transaction_pooler(url: str) -> bool:
    lowered = url.lower()
    return (
        "pooler.supabase.com" in lowered
        or ":6543/" in lowered
        or "pgbouncer=true" in lowered
        or "pool_mode=transaction" in lowered
    )


def _psycopg_connect_args(url: str, env: Literal["dev", "test", "prod"]) -> dict[str, object]:
    # Psycopg automatic prepared statements can break behind transaction poolers
    # such as Supabase/PgBouncer. Disable them for dev/test and for known pooler URLs.
    if not _is_psycopg_postgres(url):
        return {}
    if env in {"dev", "test"} or _uses_transaction_pooler(url):
        return {"prepare_threshold": None}
    return {}


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or settings.database_url
    engine_kwargs: dict[str, object] = {
        "pool_pre_ping": settings.db_pool_pre_ping,
        "future": True,
    }
    connect_args = _psycopg_connect_args(url, settings.env)
    if connect_args:
        engine_kwargs["connect_args"] = connect_args
    if not _is_sqlite(url):
        engine_kwargs.update(
            {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_recycle": settings.db_pool_recycle,
            }
        )
    return create_engine(url, **engine_kwargs)


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def _apply_rls_session_settings(
    session: Session,
    transaction: object,
    connection,
) -> None:
    clinic_id = get_current_clinic_id()
    is_platform_admin = get_current_is_platform_admin()
    clinic_value = "" if clinic_id is None else str(clinic_id)
    connection.execute(
        text(
            """
            SELECT
                set_config('row_security', 'on', true),
                set_config('app.current_clinic_id', :clinic_id, true),
                set_config('app.is_platform_admin', :is_admin, true)
            """
        ),
        {
            "clinic_id": clinic_value,
            "is_admin": "true" if is_platform_admin else "false",
        },
    )
    mark_rls_state(
        session,
        clinic_value,
        is_platform_admin,
        transaction=transaction,
    )


@event.listens_for(Session, "after_transaction_end")
def _clear_rls_session_settings(
    session: Session,
    transaction: object,
) -> None:
    clear_rls_state(session, transaction)


def _track_session_open() -> tuple[str | None, int]:
    request_id = request_id_ctx.get()
    if not request_id or request_id == "-":
        return None, 0
    with _session_count_lock:
        count = _request_session_counts.get(request_id, 0) + 1
        _request_session_counts[request_id] = count
    return request_id, count


def _track_session_close(request_id: str | None) -> None:
    if not request_id:
        return
    with _session_count_lock:
        count = _request_session_counts.get(request_id, 0)
        if count <= 1:
            _request_session_counts.pop(request_id, None)
            return
        _request_session_counts[request_id] = count - 1


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    request_id, count = _track_session_open()
    if request_id and count > 1:
        logger.warning(
            "multiple db sessions created for request_id=%s count=%s",
            request_id,
            count,
        )
    try:
        yield db
    finally:
        db.close()
        _track_session_close(request_id)
