"""Admin policy link endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.logging import error_payload
from app.db.models import (
    Agency,
    AgencyProcedurePolicyLink,
    PolicyLinkStatus,
    ProcedureCode,
    User,
)
from app.db.session import get_db
from app.schemas.admin_catalogs import (
    PolicyLinkCreateRequest,
    PolicyLinkResponse,
    PolicyLinkUpdateRequest,
)

router = APIRouter(prefix="/api/admin/policy-links", tags=["admin_policy_links"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


def _ensure_active_unique(
    db: Session,
    agency_id: uuid.UUID,
    procedure_code_id: uuid.UUID,
    status_value: PolicyLinkStatus,
    exclude_id: uuid.UUID | None = None,
) -> JSONResponse | None:
    if status_value != PolicyLinkStatus.ACTIVE:
        return None
    stmt = select(AgencyProcedurePolicyLink).where(
        AgencyProcedurePolicyLink.agency_id == agency_id,
        AgencyProcedurePolicyLink.procedure_code_id == procedure_code_id,
        AgencyProcedurePolicyLink.status == PolicyLinkStatus.ACTIVE,
    )
    if exclude_id is not None:
        stmt = stmt.where(AgencyProcedurePolicyLink.id != exclude_id)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="POLICY_LINK_EXISTS",
                message="Active policy link already exists",
                details={"agency_id": str(agency_id), "procedure_code_id": str(procedure_code_id)},
            ),
        )
    return None


@router.get("", response_model=list[PolicyLinkResponse])
def list_policy_links(
    db: DbSessionDep,
    _: AdminUserDep,
    agency_id: Annotated[uuid.UUID | None, Query()] = None,
    procedure_code_id: Annotated[uuid.UUID | None, Query()] = None,
    query: Annotated[str | None, Query()] = None,
) -> list[PolicyLinkResponse]:
    stmt = select(AgencyProcedurePolicyLink)
    if agency_id:
        stmt = stmt.where(AgencyProcedurePolicyLink.agency_id == agency_id)
    if procedure_code_id:
        stmt = stmt.where(AgencyProcedurePolicyLink.procedure_code_id == procedure_code_id)
    if query:
        like = f"%{query}%"
        stmt = stmt.join(ProcedureCode).where(
            AgencyProcedurePolicyLink.policy_url.ilike(like)
            | AgencyProcedurePolicyLink.notes.ilike(like)
            | ProcedureCode.code.ilike(like)
        )
    links = db.execute(stmt.order_by(AgencyProcedurePolicyLink.updated_at.desc())).scalars().all()
    return [PolicyLinkResponse.model_validate(link) for link in links]


@router.post("", response_model=PolicyLinkResponse, status_code=status.HTTP_201_CREATED)
def create_policy_link(
    payload: PolicyLinkCreateRequest,
    db: DbSessionDep,
    _: AdminUserDep,
) -> PolicyLinkResponse | JSONResponse:
    agency = db.execute(select(Agency).where(Agency.id == payload.agency_id)).scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    procedure_code = db.execute(
        select(ProcedureCode).where(ProcedureCode.id == payload.procedure_code_id)
    ).scalar_one_or_none()
    if procedure_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Procedure code not found"
        )
    conflict = _ensure_active_unique(
        db, payload.agency_id, payload.procedure_code_id, payload.status
    )
    if conflict is not None:
        return conflict
    link = AgencyProcedurePolicyLink(
        agency_id=payload.agency_id,
        procedure_code_id=payload.procedure_code_id,
        policy_url=str(payload.policy_url),
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        status=payload.status,
        notes=payload.notes,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return PolicyLinkResponse.model_validate(link)


@router.patch("/{policy_link_id}", response_model=PolicyLinkResponse)
def update_policy_link(
    policy_link_id: uuid.UUID,
    payload: PolicyLinkUpdateRequest,
    db: DbSessionDep,
    _: AdminUserDep,
) -> PolicyLinkResponse | JSONResponse:
    link = db.execute(
        select(AgencyProcedurePolicyLink).where(AgencyProcedurePolicyLink.id == policy_link_id)
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy link not found")
    data = payload.model_dump(exclude_unset=True)
    agency_id = data.get("agency_id", link.agency_id)
    procedure_code_id = data.get("procedure_code_id", link.procedure_code_id)
    status_value = data.get("status", link.status)
    if "agency_id" in data:
        agency = db.execute(select(Agency).where(Agency.id == agency_id)).scalar_one_or_none()
        if agency is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    if "procedure_code_id" in data:
        procedure_code = db.execute(
            select(ProcedureCode).where(ProcedureCode.id == procedure_code_id)
        ).scalar_one_or_none()
        if procedure_code is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Procedure code not found"
            )
    conflict = _ensure_active_unique(db, agency_id, procedure_code_id, status_value, link.id)
    if conflict is not None:
        return conflict
    if "policy_url" in data and data["policy_url"] is not None:
        data["policy_url"] = str(data["policy_url"])
    for field, value in data.items():
        setattr(link, field, value)
    db.add(link)
    db.commit()
    db.refresh(link)
    return PolicyLinkResponse.model_validate(link)


@router.delete(
    "/{policy_link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_policy_link(
    policy_link_id: uuid.UUID,
    db: DbSessionDep,
    _: AdminUserDep,
) -> Response:
    link = db.execute(
        select(AgencyProcedurePolicyLink).where(AgencyProcedurePolicyLink.id == policy_link_id)
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy link not found")
    db.delete(link)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
