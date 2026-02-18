"""Admin patient read-only endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_platform_staff_admin
from app.core import policy
from app.db.models import User
from app.db.session import get_db
from app.repositories.patients import list_patients_query
from app.schemas.admin_dashboard import AdminPatientSummary

router = APIRouter(prefix="/api/admin/patients", tags=["admin_patients"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_platform_staff_admin)]


@router.get("", response_model=list[AdminPatientSummary])
def list_patients(
    db: DbSessionDep,
    current_user: AdminUserDep,
    query: Annotated[str | None, Query()] = None,
) -> list[AdminPatientSummary]:
    clinic_id = None if policy.is_platform_staff_admin(current_user) else current_user.clinic_id
    patients = list_patients_query(db, clinic_id=clinic_id, doctor_id=None, query=query)
    return [AdminPatientSummary.model_validate(patient) for patient in patients]
