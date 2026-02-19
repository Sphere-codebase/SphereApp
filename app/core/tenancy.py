"""Tenant context helpers."""

from __future__ import annotations

import contextvars

from sqlalchemy import text
from sqlalchemy.orm import Session

clinic_id_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "clinic_id", default=None
)
is_platform_admin_ctx: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "is_platform_admin", default=False
)


def set_current_clinic_id(clinic_id: int | None) -> contextvars.Token[int | None]:
    return clinic_id_ctx.set(clinic_id)


def reset_current_clinic_id(token: contextvars.Token[int | None]) -> None:
    clinic_id_ctx.reset(token)


def get_current_clinic_id() -> int | None:
    return clinic_id_ctx.get()


def set_current_is_platform_admin(value: bool) -> contextvars.Token[bool]:
    return is_platform_admin_ctx.set(value)


def reset_current_is_platform_admin(token: contextvars.Token[bool]) -> None:
    is_platform_admin_ctx.reset(token)


def get_current_is_platform_admin() -> bool:
    return is_platform_admin_ctx.get()


def apply_rls_context(db: Session, clinic_id: int | None, is_platform_admin: bool) -> None:
    clinic_value = "" if clinic_id is None else str(clinic_id)
    db.execute(
        text("SELECT set_config('app.current_clinic_id', :clinic_id, true)"),
        {"clinic_id": clinic_value},
    )
    db.execute(
        text("SELECT set_config('app.is_platform_admin', :is_admin, true)"),
        {"is_admin": "true" if is_platform_admin else "false"},
    )
