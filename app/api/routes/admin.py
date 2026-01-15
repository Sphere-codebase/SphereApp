"""Admin-only JSON endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_admin
from app.core.logging import error_payload
from app.core.security import get_password_hash
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole
from app.db.session import get_db
from app.schemas.admin_users import (
    AdminUserCreateRequest,
    AdminUserResetPasswordRequest,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from app.utils.time import utcnow

router = APIRouter(prefix="/api/admin", tags=["admin"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    db: DbSessionDep,
    current_user: AdminUserDep,
    query: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    role: Annotated[str | None, Query()] = None,
) -> list[AdminUserResponse]:
    stmt = select(User).options(selectinload(User.roles))
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if role:
        stmt = stmt.join(User.roles).where(Role.code == role)
    users = db.execute(stmt.order_by(User.email.asc())).scalars().all()
    return [
        AdminUserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=bool(user.is_active),
            roles=[item.code for item in user.roles],
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
    user = db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=bool(user.is_active),
        roles=[item.code for item in user.roles],
        created_at=user.created_at,
    )


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AdminUserResponse | JSONResponse:
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
    assigned_roles = ["doctor"]
    if is_admin:
        assigned_roles.append("admin")
    doctor_role = _ensure_role(db, "doctor", "Default doctor role")
    admin_role = _ensure_role(db, "admin", "Administrator role") if is_admin else None
    user = User(
        id=next_id(db, User),
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        is_active=payload.is_active,
        created_at=utcnow(),
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    if admin_role is not None:
        db.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db.commit()
    db.refresh(user)
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
) -> AdminUserResponse | JSONResponse:
    user = db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    ).scalar_one_or_none()
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
        role_codes = {role.strip().lower() for role in data["roles"] if role}
        if "doctor" not in role_codes:
            role_codes.add("doctor")
        if user.id == current_user.id and "admin" not in role_codes:
            admin_count = db.execute(
                select(func.count())
                .select_from(UserRole)
                .join(Role)
                .where(Role.code == "admin")
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
        db.execute(
            UserRole.__table__.delete().where(UserRole.user_id == user.id)
        )
        for code in sorted(role_codes):
            role = _ensure_role(db, code, code.capitalize())
            db.add(UserRole(user_id=user.id, role_id=role.id))
    db.add(user)
    db.commit()
    refreshed = db.execute(
        select(User)
        .options(selectinload(User.roles))
        .execution_options(populate_existing=True)
        .where(User.id == user.id)
    ).scalar_one()
    return AdminUserResponse(
        id=refreshed.id,
        email=refreshed.email,
        full_name=refreshed.full_name,
        is_active=bool(refreshed.is_active),
        roles=[role.code for role in refreshed.roles],
        created_at=refreshed.created_at,
    )


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    payload: AdminUserResetPasswordRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> Response:
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.password_hash = get_password_hash(payload.password)
    db.add(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _ensure_role(db: Session, code: str, description: str) -> Role:
    existing = db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
    if existing is not None:
        return existing
    role = Role(id=next_id(db, Role), code=code, description=description)
    db.add(role)
    db.flush()
    return role
