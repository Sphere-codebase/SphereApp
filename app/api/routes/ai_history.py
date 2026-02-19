"""AI history endpoints."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUserDep, require_roles
from app.core import policy
from app.db.models import AuditLog, User
from app.db.session import get_db
from app.schemas.ai_history import AIHistoryItem, AIHistoryResponse

router = APIRouter(prefix="/api/ai-history", tags=["ai_history"])
DbSessionDep = Annotated[Session, Depends(get_db)]

AI_ACTIONS = {
    "ai_proposal_confirmed",
    "ai_proposal_rejected",
    "claim.finalized",
    "claim.pdf_generated",
}


@router.get("", response_model=AIHistoryResponse)
def list_ai_history(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    actor_id: Annotated[int | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    claim_id: Annotated[int | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AIHistoryResponse:
    require_roles("doctor", "chief_doctor", "clinic_admin")(current_user)

    filters = [
        AuditLog.clinic_id == current_user.clinic_id,
        AuditLog.scope == "clinic",
        or_(AuditLog.action.ilike("ai_%"), AuditLog.action.in_(AI_ACTIONS)),
    ]

    if policy.role_for(current_user) == policy.Role.DOCTOR:
        filters.append(AuditLog.actor_id == current_user.id)
    elif actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)

    if action:
        filters.append(AuditLog.action == action)
    if claim_id is not None:
        filters.append(AuditLog.entity_id == str(claim_id))
    if date_from:
        filters.append(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        filters.append(AuditLog.created_at <= datetime.combine(date_to, time.max))

    total = db.execute(select(func.count()).select_from(AuditLog).where(*filters)).scalar_one()

    rows = (
        db.execute(
            select(AuditLog, User.full_name, User.email)
            .join(User, User.id == AuditLog.actor_id, isouter=True)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .all()
    )

    items = []
    for log, full_name, email in rows:
        items.append(
            AIHistoryItem(
                id=log.id,
                created_at=log.created_at,
                actor_id=log.actor_id,
                actor_name=full_name or email,
                action=log.action,
                entity=log.entity,
                entity_id=log.entity_id,
                diff_json=log.diff_json,
                request_id=log.request_id,
            )
        )

    return AIHistoryResponse(items=items, limit=limit, offset=offset, total=total)
