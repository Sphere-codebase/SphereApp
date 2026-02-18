"""Audit log endpoints."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUserDep, require_platform_staff_admin
from app.core import policy
from app.db.models import AuditLog, User
from app.db.session import get_db
from app.schemas.audit_logs import AuditLogResponse

clinic_router = APIRouter(prefix="/api/clinic/audit-logs", tags=["clinic_audit_logs"])
admin_router = APIRouter(prefix="/api/admin/audit-logs", tags=["admin_audit_logs"])

DbSessionDep = Annotated[Session, Depends(get_db)]


def _apply_common_filters(
    stmt,
    *,
    actor_id: int | None,
    action: str | None,
    entity: str | None,
    entity_id: str | None,
    request_id: str | None,
    date_from: date | None,
    date_to: date | None,
):
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if request_id:
        stmt = stmt.where(AuditLog.request_id == request_id)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= datetime.combine(date_to, time.max))
    return stmt


@clinic_router.get("", response_model=list[AuditLogResponse])
def list_clinic_audit_logs(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    actor_id: Annotated[int | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    entity: Annotated[str | None, Query()] = None,
    entity_id: Annotated[str | None, Query()] = None,
    request_id: Annotated[str | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> list[AuditLogResponse]:
    if not policy.can(current_user, policy.Action.LIST, policy.Resource.AUDIT_LOG):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    stmt = select(AuditLog).where(*policy.audit_scope_filters(current_user, AuditLog))
    stmt = _apply_common_filters(
        stmt,
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        request_id=request_id,
        date_from=date_from,
        date_to=date_to,
    )
    rows = db.execute(stmt.order_by(AuditLog.created_at.desc())).scalars().all()
    return [AuditLogResponse.model_validate(row) for row in rows]


@admin_router.get("", response_model=list[AuditLogResponse])
def list_admin_audit_logs(
    db: DbSessionDep,
    current_user: Annotated[User, Depends(require_platform_staff_admin)],
    actor_id: Annotated[int | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    entity: Annotated[str | None, Query()] = None,
    entity_id: Annotated[str | None, Query()] = None,
    request_id: Annotated[str | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    target_clinic_id: Annotated[int | None, Query()] = None,
) -> list[AuditLogResponse]:
    stmt = select(AuditLog)
    if target_clinic_id is not None:
        stmt = stmt.where(
            or_(
                AuditLog.target_clinic_id == target_clinic_id,
                AuditLog.clinic_id == target_clinic_id,
            )
        )
    stmt = _apply_common_filters(
        stmt,
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        request_id=request_id,
        date_from=date_from,
        date_to=date_to,
    )
    rows = db.execute(stmt.order_by(AuditLog.created_at.desc())).scalars().all()
    return [AuditLogResponse.model_validate(row) for row in rows]
