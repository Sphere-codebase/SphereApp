"""Tenant context helpers."""

from __future__ import annotations

import contextvars
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

clinic_id_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "clinic_id", default=None
)
is_platform_admin_ctx: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "is_platform_admin", default=False
)

_RLS_ROLE_READY: set[str] = set()


def _is_test_env() -> bool:
    return os.getenv("ENV") == "test"


def _ensure_rls_role(db: Session) -> None:
    global _RLS_ROLE_READY
    from app.core.config import settings

    if not _is_test_env() and settings.env != "test":
        return
    db_name = db.execute(text("SELECT current_database()")).scalar_one()
    if db_name in _RLS_ROLE_READY:
        return
    db.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rls') THEN
                    CREATE ROLE app_rls;
                END IF;
            END $$;
            """
        )
    )
    db.execute(text("GRANT USAGE ON SCHEMA public TO app_rls"))
    db.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_rls"))
    db.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rls"))
    db.execute(
        text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rls"
        )
    )
    _RLS_ROLE_READY.add(db_name)


def set_current_clinic_id(clinic_id: int | None) -> int | None:
    previous = clinic_id_ctx.get()
    clinic_id_ctx.set(clinic_id)
    return previous


def reset_current_clinic_id(previous: int | None) -> None:
    clinic_id_ctx.set(previous)


def get_current_clinic_id() -> int | None:
    return clinic_id_ctx.get()


def set_current_is_platform_admin(value: bool) -> bool:
    previous = is_platform_admin_ctx.get()
    is_platform_admin_ctx.set(value)
    return previous


def reset_current_is_platform_admin(previous: bool) -> None:
    is_platform_admin_ctx.set(previous)


def get_current_is_platform_admin() -> bool:
    return is_platform_admin_ctx.get()


def apply_rls_context(db: Session, clinic_id: int | None, is_platform_admin: bool) -> None:
    from app.core.config import settings

    clinic_value = "" if clinic_id is None else str(clinic_id)
    db.execute(text("SELECT set_config('row_security', 'on', true)"))
    _ensure_rls_role(db)
    if _is_test_env() or settings.env == "test":
        db.execute(text("SET ROLE app_rls"))
    db.execute(
        text("SELECT set_config('app.current_clinic_id', :clinic_id, true)"),
        {"clinic_id": clinic_value},
    )
    db.execute(
        text("SELECT set_config('app.is_platform_admin', :is_admin, true)"),
        {"is_admin": "true" if is_platform_admin else "false"},
    )
