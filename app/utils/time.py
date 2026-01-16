"""Time helpers."""

from __future__ import annotations

from datetime import datetime


def utcnow() -> datetime:
    """Return naive UTC timestamp for storage in timestamp columns."""
    return datetime.utcnow()
