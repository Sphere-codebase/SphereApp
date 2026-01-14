"""Admin-only JSON endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.logging import error_payload
from app.core.security import get_password_hash
from app.db.models import User
from app.db.session import get_db
from app.schemas.admin_users import (
    AdminUserCreateRequest,
    AdminUserResetPasswordRequest,
    AdminUserResponse,
    AdminUserUpdateRequest,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    db: DbSessionDep,
    current_user: AdminUserDep,
    query: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    is_admin: Annotated[bool | None, Query()] = None,
) -> list[AdminUserResponse]:
    stmt = select(User).where(User.tenant_id == current_user.tenant_id)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if is_admin is not None:
        stmt = stmt.where(User.is_admin == is_admin)
    users = db.execute(stmt.order_by(User.email.asc())).scalars().all()
    return [AdminUserResponse.model_validate(user) for user in users]


@router.get("/users/{user_id}", response_model=AdminUserResponse)
def get_user(
    user_id: uuid.UUID,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AdminUserResponse:
    user = db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AdminUserResponse.model_validate(user)


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AdminUserResponse | JSONResponse:
    existing = db.execute(
        select(User).where(
            User.email == payload.email,
            User.tenant_id == current_user.tenant_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="USER_ALREADY_EXISTS",
                message="User already exists",
                details={"email": payload.email},
            ),
        )

    user = User(
        tenant_id=current_user.tenant_id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        is_active=payload.is_active,
        is_admin=payload.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AdminUserResponse | JSONResponse:
    user = db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        existing = db.execute(
            select(User).where(
                User.email == data["email"],
                User.tenant_id == current_user.tenant_id,
                User.id != user.id,
            )
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
    if data.get("is_admin") is False and user.id == current_user.id:
        admin_count = db.execute(
            select(func.count()).select_from(User).where(
                User.tenant_id == current_user.tenant_id,
                User.is_admin.is_(True),
            )
        ).scalar_one()
        if int(admin_count) <= 1:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="LAST_ADMIN",
                    message="Cannot remove the last admin",
                    details={"user_id": str(user.id)},
                ),
            )
    for field, value in data.items():
        setattr(user, field, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: uuid.UUID,
    payload: AdminUserResetPasswordRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> Response:
    user = db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.hashed_password = get_password_hash(payload.password)
    db.add(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
