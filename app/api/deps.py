"""API dependency helpers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session

from app.core import policy
from app.core.config import settings
from app.core.security import get_current_user
from app.core.tenancy import apply_rls_context, reset_current_is_platform_admin, set_current_is_platform_admin
from app.db.models import User
from app.db.session import get_db
from app.services.audit import AuditContext, AuditLogger

CurrentUserDep = Annotated[User, Depends(get_current_user)]
DbSessionDep = Annotated[Session, Depends(get_db)]


def get_audit_logger(request: Request, db: DbSessionDep) -> AuditLogger:
    return AuditLogger(db=db, context=AuditContext.from_request(request))


AuditLoggerDep = Annotated[AuditLogger, Depends(get_audit_logger)]


def require_platform_staff_admin(
    current_user: CurrentUserDep,
    db: DbSessionDep,
):
    if not policy.can(current_user, policy.Action.READ, policy.Resource.ADMIN_DIRECTORY):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    previous_is_admin = set_current_is_platform_admin(True)
    apply_rls_context(db, current_user.clinic_id, True)
    try:
        yield current_user
    finally:
        reset_current_is_platform_admin(previous_is_admin)


def require_roles(*roles: str):
    def _dependency(current_user: CurrentUserDep) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return current_user

    return _dependency


def require_agent_token(
    x_agent_token: Annotated[str | None, Header(alias="X-Agent-Token")] = None,
) -> None:
    if not settings.agent_api_key or x_agent_token != settings.agent_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent token required")
