"""Insurance company list endpoints for patient intake."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.patients import InsuranceCompanyListResponse
from app.services.patients import InsuranceCompanyListFilters, PatientService

router = APIRouter(prefix="/api/insurance-companies", tags=["insurance_companies"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=InsuranceCompanyListResponse)
def list_insurance_companies(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InsuranceCompanyListResponse:
    service = PatientService(db)
    return service.list_insurance_companies(
        filters=InsuranceCompanyListFilters(q=q, limit=limit, offset=offset)
    )
