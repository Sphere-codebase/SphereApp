"""Helpers for deterministic bigint IDs."""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session


def _lock_next_id_namespace(db: Session, model: type) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": model.__table__.fullname},
    )


def _run_as_platform_admin(db: Session, callback):
    prev = db.execute(
        text("SELECT current_setting('app.is_platform_admin', true)")
    ).scalar_one_or_none()
    db.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))
    try:
        return callback()
    finally:
        restore = prev if prev is not None else "false"
        db.execute(
            text("SELECT set_config('app.is_platform_admin', :prev, true)"),
            {"prev": restore},
        )


def next_ids(db: Session, model: type, count: int) -> list[int]:
    if count <= 0:
        return []

    def allocate() -> list[int]:
        _lock_next_id_namespace(db, model)
        value = db.execute(select(func.coalesce(func.max(model.id), 0))).scalar_one()
        start = int(value) + 1
        return list(range(start, start + count))

    return _run_as_platform_admin(db, allocate)


def next_id(db: Session, model: type) -> int:
    return next_ids(db, model, 1)[0]
