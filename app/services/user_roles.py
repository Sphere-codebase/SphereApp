"""Helpers for user role normalization and assignment."""

from __future__ import annotations

from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import error_payload
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole

ROLE_ALIASES = {
    "admin": "platform_staff_admin",
    "platform_admin": "platform_staff_admin",
}

ROLE_PRIORITY = {
    "platform_staff_admin": 3,
    "clinic_admin": 2,
    "chief_doctor": 1,
    "doctor": 0,
}


def normalize_roles(roles: list[str] | None) -> list[str]:
    if not roles:
        return []
    normalized: list[str] = []
    for role in roles:
        if not role or not role.strip():
            continue
        key = role.strip().lower()
        key = ROLE_ALIASES.get(key, key)
        if key in ROLE_PRIORITY:
            normalized.append(key)
    return normalized


def is_admin_role(roles: list[str] | None) -> bool:
    return resolve_primary_role(roles) == "platform_staff_admin"


def resolve_primary_role(roles: list[str] | None) -> str:
    normalized = normalize_roles(roles)
    if not normalized:
        return "doctor"
    return max(normalized, key=lambda role: ROLE_PRIORITY[role])


def assigned_roles_for_user(primary_role: str) -> list[str]:
    return [primary_role]


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
    primary_role = resolve_primary_role(role_codes)
    db.execute(UserRole.__table__.delete().where(UserRole.user_id == user_id))
    role = ensure_role(db, primary_role, primary_role.replace("_", " ").title())
    db.add(UserRole(user_id=user_id, role_id=role.id))
    db.execute(User.__table__.update().where(User.id == user_id).values(role=primary_role))
