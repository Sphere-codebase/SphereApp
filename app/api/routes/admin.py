"""Admin-only JSON endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import error_payload
from app.core.security import create_access_token, get_current_user, get_password_hash
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import AdminCreateUserRequest, AdminCreateUserResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def _is_admin_role(role: str | None) -> bool:
    if role is None:
        return False
    return role.strip().lower() in {"admin", "administrator"}


@router.post("/users", response_model=AdminCreateUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminCreateUserRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> AdminCreateUserResponse | JSONResponse:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

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

    user = User(
        tenant_id=current_user.tenant_id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        is_active=True,
        is_admin=_is_admin_role(payload.role),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id))
    return AdminCreateUserResponse(
        access_token=token,
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )
