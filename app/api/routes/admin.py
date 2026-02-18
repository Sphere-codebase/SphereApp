"""Admin-only JSON endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep, require_platform_staff_admin
from app.core.logging import error_payload
from app.core.security import get_password_hash
from app.db.id_utils import next_id
from app.db.models import User, UserRole
from app.db.session import get_db
from app.schemas.admin_users import (
    AdminUserCreateRequest,
    AdminUserResetPasswordRequest,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from app.services.user_roles import (
    assigned_roles_for_user,
    ensure_role,
    resolve_primary_role,
    set_user_roles,
    user_already_exists_response,
)
from app.utils.time import utcnow

router = APIRouter(prefix="/api/admin", tags=["admin"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_platform_staff_admin)]


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    db: DbSessionDep,
    current_user: AdminUserDep,
    query: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    role: Annotated[str | None, Query()] = None,
) -> list[AdminUserResponse]:
    stmt = select(User)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if role:
        stmt = stmt.where(User.role == role)
    users = db.execute(stmt.order_by(User.email.asc())).scalars().all()
    return [
        AdminUserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=bool(user.is_active),
            roles=[user.role],
            created_at=user.created_at,
        )
        for user in users
    ]


@router.get("/users/{user_id}", response_model=AdminUserResponse)
def get_user(
    user_id: int,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AdminUserResponse:
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=bool(user.is_active),
        roles=[user.role],
        created_at=user.created_at,
    )


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,  # не используется
    audit: AuditLoggerDep,
) -> AdminUserResponse | JSONResponse:
    existing_response = user_already_exists_response(db, payload.email)
    if existing_response is not None:
        return existing_response

    primary_role = resolve_primary_role(payload.roles)
    assigned_roles = assigned_roles_for_user(primary_role)
    role_row = ensure_role(db, primary_role, primary_role.replace("_", " ").title())
    user = User(
        id=next_id(db, User),
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        is_active=payload.is_active,
        role=primary_role,
        created_at=utcnow(),
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role_row.id))
    db.commit()
    db.refresh(user)
    audit.log_event(
        action="CREATE",
        entity="user",
        entity_id=user.id,
        actor=current_user,
        clinic_id=user.clinic_id,
        target_clinic_id=user.clinic_id,
        target_user_id=user.id,
        diff={"fields": ["full_name", "is_active", "role"]},
        scope="platform",
    )
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=bool(user.is_active),
        roles=assigned_roles,
        created_at=user.created_at,
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> AdminUserResponse | JSONResponse:
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        existing = db.execute(
            select(User).where(User.email == data["email"], User.id != user.id)
        ).scalar_one_or_none()
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="USER_EMAIL_EXISTS",
                    message="User email already exists",
                    details={"email": data["email"]},
                ),
            )
    for field, value in data.items():
        if field != "roles":
            setattr(user, field, value)
    if "roles" in data and data["roles"] is not None:
        primary_role = resolve_primary_role(data["roles"])
        if user.id == current_user.id and user.role == "platform_staff_admin":
            admin_count = db.execute(
                select(func.count())
                .select_from(User)
                .where(User.role == "platform_staff_admin")
            ).scalar_one()
            if int(admin_count or 0) <= 1:
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content=error_payload(
                        code="LAST_ADMIN",
                        message="Cannot remove the last admin",
                        details={"user_id": str(user.id)},
                    ),
                )
        user.role = primary_role
        set_user_roles(db, user.id, [primary_role])
    db.add(user)
    db.commit()
    refreshed = db.execute(select(User).where(User.id == user.id)).scalar_one()
    audit_fields = [field for field in data.keys() if field != "password"]
    audit.log_event(
        action="UPDATE",
        entity="user",
        entity_id=refreshed.id,
        actor=current_user,
        clinic_id=refreshed.clinic_id,
        target_clinic_id=refreshed.clinic_id,
        target_user_id=refreshed.id,
        diff={"fields": audit_fields},
        scope="platform",
    )
    return AdminUserResponse(
        id=refreshed.id,
        email=refreshed.email,
        full_name=refreshed.full_name,
        is_active=bool(refreshed.is_active),
        roles=[refreshed.role],
        created_at=refreshed.created_at,
    )


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    payload: AdminUserResetPasswordRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> Response:
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.password_hash = get_password_hash(payload.password)
    db.add(user)
    db.commit()
    audit.log_event(
        action="UPDATE",
        entity="user",
        entity_id=user.id,
        actor=current_user,
        clinic_id=user.clinic_id,
        target_clinic_id=user.clinic_id,
        target_user_id=user.id,
        diff={"fields": ["password"]},
        scope="platform",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
