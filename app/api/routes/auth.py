"""Authentication routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep
from app.core.config import settings
from app.core.response_cache import auth_me_response_cache
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
from app.services.user_roles import (
    assigned_roles_for_user,
    ensure_role,
    resolve_primary_role,
    user_already_exists_response,
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
def login(payload: LoginRequest, db: DbSessionDep, audit: AuditLoggerDep) -> TokenResponse:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")

    token = create_access_token(str(user.id))
    audit.log_event(
        action="LOGIN",
        entity="user",
        entity_id=user.id,
        actor=user,
        target_user_id=user.id,
        target_clinic_id=user.clinic_id,
        diff={"method": "password"},
    )
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
    audit: AuditLoggerDep,
) -> AdminCreateUserResponse | JSONResponse:
    if not settings.admin_api_key or admin_token != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token required")

    existing_response = user_already_exists_response(db, payload.email)
    if existing_response is not None:
        return existing_response

    primary_role = resolve_primary_role(payload.roles)
    role_row = ensure_role(db, primary_role, primary_role.replace("_", " ").title())
    assigned_roles = assigned_roles_for_user(primary_role)
    user = User(
        id=next_id(db, User),
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        is_active=True,
        role=primary_role,
        created_at=utcnow(),
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role_row.id))
    db.commit()

    token = create_access_token(str(user.id))
    audit.log_event(
        action="CREATE",
        entity="user",
        entity_id=user.id,
        actor=None,
        clinic_id=user.clinic_id,
        target_clinic_id=user.clinic_id,
        target_user_id=user.id,
        scope="platform",
        diff={"fields": ["full_name", "is_active", "role"]},
    )
    return AdminCreateUserResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        roles=assigned_roles,
    )


@router.post("/dev-token", response_model=TokenResponse)
def dev_token(payload: DevTokenRequest, db: DbSessionDep, audit: AuditLoggerDep) -> TokenResponse:
    if settings.env not in {"dev", "test"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not available")

    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    token = create_access_token(str(user.id))
    audit.log_event(
        action="LOGIN",
        entity="user",
        entity_id=user.id,
        actor=user,
        target_user_id=user.id,
        target_clinic_id=user.clinic_id,
        diff={"method": "dev-token"},
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUserDep, db: DbSessionDep) -> UserResponse:
    cache_key = (
        "auth_me",
        current_user.id,
        current_user.clinic_id,
        current_user.role,
        current_user.role == "platform_staff_admin",
    )

    def _load_payload() -> dict[str, object]:
        roles = (
            db.execute(
                select(Role.code)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == current_user.id)
                .order_by(Role.code.asc())
            )
            .scalars()
            .all()
        )
        if not roles and current_user.role:
            roles = [current_user.role]
        response = UserResponse(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            role=current_user.role,
            roles=roles,
            clinic_id=current_user.clinic_id,
            clinic_name=current_user.clinic.name if current_user.clinic else None,
            is_active=bool(current_user.is_active),
        )
        return response.model_dump(mode="json")

    payload = auth_me_response_cache.get_or_set(
        cache_key,
        settings.auth_me_cache_ttl_seconds,
        _load_payload,
    )
    return UserResponse.model_validate(payload)
