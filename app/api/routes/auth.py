"""Authentication routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import error_payload
from app.core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole
from app.db.session import get_db
from app.schemas.auth import (
    AdminCreateUserRequest,
    AdminCreateUserResponse,
    DevTokenRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from app.utils.time import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
def get_admin_token(
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> str | None:
    return x_admin_token


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSessionDep) -> TokenResponse:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post(
    "/admin/users",
    response_model=AdminCreateUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: AdminCreateUserRequest,
    db: DbSessionDep,
    admin_token: Annotated[str | None, Depends(get_admin_token)],
) -> AdminCreateUserResponse | JSONResponse:
    if not settings.admin_api_key or admin_token != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token required")

    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="USER_ALREADY_EXISTS",
                message="User already exists",
                details={"email": payload.email},
            ),
        )

    roles = payload.roles or []
    is_admin = any(role.strip().lower() == "admin" for role in roles)
    doctor_role = _ensure_role(db, "doctor", "Default doctor role")
    admin_role = _ensure_role(db, "admin", "Administrator role") if is_admin else None
    assigned_roles = ["doctor"]
    if is_admin:
        assigned_roles.append("admin")
    user = User(
        id=next_id(db, User),
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        is_active=True,
        created_at=utcnow(),
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    if admin_role is not None:
        db.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db.commit()

    token = create_access_token(str(user.id))
    return AdminCreateUserResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        roles=assigned_roles,
    )


@router.post("/dev-token", response_model=TokenResponse)
def dev_token(payload: DevTokenRequest, db: DbSessionDep) -> TokenResponse:
    if settings.env not in {"dev", "test"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not available")

    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUserDep) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        is_active=bool(current_user.is_active),
        roles=[role.code for role in current_user.roles],
    )


def _ensure_role(db: Session, code: str, description: str) -> Role:
    existing = db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
    if existing is not None:
        return existing
    role = Role(id=next_id(db, Role), code=code, description=description)
    db.add(role)
    db.flush()
    return role
