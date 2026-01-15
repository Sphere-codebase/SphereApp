"""Admin agencies endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.logging import error_payload
from app.db.models import Agency, User
from app.db.session import get_db
from app.schemas.admin_catalogs import (
    AgencyCreateRequest,
    AgencyResponse,
    AgencyUpdateRequest,
)

router = APIRouter(prefix="/api/admin/agencies", tags=["admin_agencies"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[AgencyResponse])
def list_agencies(db: DbSessionDep, current_user: AdminUserDep) -> list[AgencyResponse]:
    agencies = (
        db.execute(
            select(Agency)
            .where(Agency.tenant_id == current_user.tenant_id)
            .order_by(Agency.name.asc())
        )
        .scalars()
        .all()
    )
    return [AgencyResponse.model_validate(agency) for agency in agencies]


@router.post("", response_model=AgencyResponse, status_code=status.HTTP_201_CREATED)
def create_agency(
    payload: AgencyCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AgencyResponse | JSONResponse:
    existing = db.execute(
        select(Agency).where(
            Agency.slug == payload.slug,
            Agency.tenant_id == current_user.tenant_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="AGENCY_EXISTS",
                message="Agency already exists",
                details={"slug": payload.slug},
            ),
        )
    agency = Agency(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        slug=payload.slug,
        is_active=payload.is_active,
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return AgencyResponse.model_validate(agency)


@router.get("/{agency_id}", response_model=AgencyResponse)
def get_agency(
    agency_id: uuid.UUID,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AgencyResponse:
    agency = db.execute(
        select(Agency).where(
            Agency.id == agency_id,
            Agency.tenant_id == current_user.tenant_id,
        )
    ).scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    return AgencyResponse.model_validate(agency)


@router.patch("/{agency_id}", response_model=AgencyResponse)
def update_agency(
    agency_id: uuid.UUID,
    payload: AgencyUpdateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AgencyResponse | JSONResponse:
    agency = db.execute(
        select(Agency).where(
            Agency.id == agency_id,
            Agency.tenant_id == current_user.tenant_id,
        )
    ).scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    if payload.slug and payload.slug != agency.slug:
        existing = (
            db.execute(
                select(Agency).where(
                    Agency.slug == payload.slug,
                    Agency.tenant_id == current_user.tenant_id,
                )
            )
            .scalar_one_or_none()
        )
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="AGENCY_EXISTS",
                    message="Agency already exists",
                    details={"slug": payload.slug},
                ),
            )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agency, field, value)
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return AgencyResponse.model_validate(agency)


@router.delete("/{agency_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_agency(
    agency_id: uuid.UUID,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> Response:
    agency = db.execute(
        select(Agency).where(
            Agency.id == agency_id,
            Agency.tenant_id == current_user.tenant_id,
        )
    ).scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    agency.is_active = False
    db.add(agency)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
