"""User repository helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import User


def upsert_user_doctor(db: Session, user: User) -> User:
    existing = db.get(User, user.id)
    if existing is None:
        db.add(user)
        return user
    return existing
