"""Helpers for deterministic bigint IDs."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def next_id(db: Session, model: type) -> int:
    value = db.execute(select(func.coalesce(func.max(model.id), 0))).scalar_one()
    return int(value) + 1
