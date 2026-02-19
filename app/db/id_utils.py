"""Helpers for deterministic bigint IDs."""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session


def next_id(db: Session, model: type) -> int:
    prev = db.execute(
        text("SELECT current_setting('app.is_platform_admin', true)")
    ).scalar_one_or_none()
    db.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))
    try:
        value = db.execute(select(func.coalesce(func.max(model.id), 0))).scalar_one()
    finally:
        restore = prev if prev is not None else "false"
        db.execute(
            text("SELECT set_config('app.is_platform_admin', :prev, true)"),
            {"prev": restore},
        )
    return int(value) + 1
