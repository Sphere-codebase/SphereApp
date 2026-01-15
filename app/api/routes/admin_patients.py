"""Admin patient read-only endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import Patient, User
from app.db.session import get_db
from app.schemas.admin_dashboard import AdminPatientSummary

router = APIRouter(prefix="/api/admin/patients", tags=["admin_patients"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[AdminPatientSummary])
def list_patients(
    db: DbSessionDep,
    current_user: AdminUserDep,
    query: Annotated[str | None, Query()] = None,
) -> list[AdminPatientSummary]:
    stmt = select(Patient)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
            )
        )
    patients = db.execute(stmt.order_by(Patient.last_name.asc())).scalars().all()
    return [AdminPatientSummary.model_validate(patient) for patient in patients]
