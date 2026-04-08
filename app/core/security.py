"""Security helpers for JWT and password hashing."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, noload

from app.core.config import settings
from app.core.exceptions import ClinicBlockedError
from app.core.tenancy import (
    apply_rls_context,
    reset_current_clinic_id,
    reset_current_is_platform_admin,
    set_current_clinic_id,
    set_current_is_platform_admin,
)
from app.db.models import User
from app.db.session import get_db
from app.services.audit import AuditContext, AuditLogger

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expires = datetime.now(tz=UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_expires_minutes)
    )
    payload = {"sub": subject, "exp": expires}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return cast(str, token)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return cast(dict[str, Any], decoded)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc


CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
DbSessionDep = Annotated[Session, Depends(get_db)]


async def get_current_user(
    credentials: CredentialsDep, db: DbSessionDep, request: Request
) -> AsyncGenerator[User, None]:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc

    # Resolve the user in a worker thread to avoid blocking the event loop.
    def _load_user() -> tuple[User | None, bool]:
        user = (
            db.execute(
                select(User)
                .options(
                    joinedload(User.clinic),
                    noload(User.roles),
                )
                .where(User.id == user_id)
            )
            .scalars()
            .one_or_none()
        )
        if user is None:
            return None, False
        is_blocked = bool(getattr(user.clinic, "is_blocked", False)) if user.clinic else False
        return user, is_blocked

    user, is_blocked = await run_in_threadpool(_load_user)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if is_blocked and user.role != "platform_staff_admin":
        try:
            audit = AuditLogger(db=db, context=AuditContext.from_request(request))
            audit.log_event(
                action="security.clinic_blocked_access_denied",
                entity="clinic",
                entity_id=user.clinic_id,
                actor=user,
                clinic_id=user.clinic_id,
                diff={"actor_id": user.id, "path": str(request.url.path)},
                scope="platform",
                actor_role=user.role,
            )
        except Exception:
            pass
        raise ClinicBlockedError(user.clinic_id)

    request.state.current_user_id = user.id
    request.state.current_user_role = user.role
    request.state.current_user_clinic_id = user.clinic_id

    # Keep ContextVar set/reset in the same async context to avoid token errors
    # when FastAPI runs sync endpoints in threadpool workers.
    is_platform_admin = user.role == "platform_staff_admin"
    previous_clinic_id = set_current_clinic_id(user.clinic_id)
    previous_is_admin = set_current_is_platform_admin(is_platform_admin)
    if settings.env == "test":
        # Tests rely on explicit role switching for strict RLS simulation.
        apply_rls_context(db, user.clinic_id, is_platform_admin)
    elif db.in_transaction():
        # End the auth lookup transaction so downstream queries begin a fresh
        # transaction and pick up tenant context once via Session after_begin.
        await run_in_threadpool(db.commit)
    try:
        yield user
    finally:
        reset_current_is_platform_admin(previous_is_admin)
        reset_current_clinic_id(previous_clinic_id)
