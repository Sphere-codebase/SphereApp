"""Tenant context helpers."""

from __future__ import annotations

import contextvars

clinic_id_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "clinic_id", default=None
)


def set_current_clinic_id(clinic_id: int | None) -> contextvars.Token[int | None]:
    return clinic_id_ctx.set(clinic_id)


def reset_current_clinic_id(token: contextvars.Token[int | None]) -> None:
    clinic_id_ctx.reset(token)


def get_current_clinic_id() -> int | None:
    return clinic_id_ctx.get()
