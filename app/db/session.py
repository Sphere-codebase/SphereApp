"""Database session utilities."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.tenancy import get_current_clinic_id, get_current_is_platform_admin


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or settings.database_url
    return create_engine(url, pool_pre_ping=True, future=True)


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
    connection.execute(text("SELECT set_config('row_security', 'on', true)"))
    connection.execute(
        text("SELECT set_config('app.current_clinic_id', :clinic_id, true)"),
        {"clinic_id": clinic_value},
    )
    connection.execute(
        text("SELECT set_config('app.is_platform_admin', :is_admin, true)"),
        {"is_admin": "true" if is_platform_admin else "false"},
    )


@event.listens_for(Engine, "checkin")
def _reset_rls_settings(dbapi_connection, _connection_record) -> None:
    """Reset tenant context on pooled connections to avoid cross-test leakage."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("RESET ROLE")
        cursor.execute("RESET app.current_clinic_id")
        cursor.execute("RESET app.is_platform_admin")
        cursor.execute("SET row_security = on")
    finally:
        cursor.close()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
