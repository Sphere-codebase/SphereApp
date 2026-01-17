"""Helpers for user role normalization and assignment."""

from __future__ import annotations

from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import error_payload
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole


def normalize_roles(roles: list[str] | None) -> list[str]:
    if not roles:
        return []
    return [role.strip().lower() for role in roles if role and role.strip()]


def is_admin_role(roles: list[str] | None) -> bool:
    return "admin" in normalize_roles(roles)


def assigned_roles_for_user(is_admin: bool) -> list[str]:
    assigned = ["doctor"]
    if is_admin:
        assigned.append("admin")
    return assigned


def user_already_exists_response(db: Session, email: str) -> JSONResponse | None:
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is None:
        return None
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_payload(
            code="USER_ALREADY_EXISTS",
            message="User already exists",
            details={"email": email},
        ),
    )


def ensure_role(db: Session, code: str, description: str) -> Role:
    existing = db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
    if existing is not None:
        return existing
    role = Role(id=next_id(db, Role), code=code, description=description)
    db.add(role)
    db.flush()
    return role


def set_user_roles(db: Session, user_id: int, role_codes: list[str]) -> None:
    db.execute(UserRole.__table__.delete().where(UserRole.user_id == user_id))
    for code in sorted(role_codes):
        role = ensure_role(db, code, code.capitalize())
        db.add(UserRole(user_id=user_id, role_id=role.id))
