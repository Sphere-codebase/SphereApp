"""Claim endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import error_payload
from app.core.security import get_current_user
from app.db.models import (
    Agency,
    AgencyProcedurePolicyLink,
    Claim,
    ClaimProcedure,
    ClaimStatus,
    Patient,
    PolicyLinkStatus,
    ProcedureCode,
    User,
    Visit,
)
from app.db.session import get_db
from app.schemas.claims import (
    ClaimCreateRequest,
    ClaimPolicyLinkItem,
    ClaimProcedureCreateRequest,
    ClaimProcedureResponse,
    ClaimResponse,
    ClaimUpdateRequest,
    ClaimVisitAttachRequest,
    ProcedureCodeSummary,
)

router = APIRouter(prefix="/api/claims", tags=["claims"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def _get_claim_or_404(db: Session, claim_id: uuid.UUID, current_user: User) -> Claim:
    claim = db.execute(
        select(Claim)
        .join(Patient)
        .where(
            Claim.id == claim_id,
            Claim.tenant_id == current_user.tenant_id,
            Patient.id == Claim.patient_id,
            Patient.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return claim


def _require_patient(db: Session, patient_id: uuid.UUID, current_user: User) -> Patient:
    patient = db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.tenant_id == current_user.tenant_id,
            Patient.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def _require_agency(db: Session, agency_id: uuid.UUID, current_user: User) -> Agency:
    agency = db.execute(
        select(Agency).where(
            Agency.id == agency_id,
            Agency.tenant_id == current_user.tenant_id,
        )
    ).scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    return agency


@router.get("", response_model=list[ClaimResponse])
def list_claims(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    patient_id: Annotated[uuid.UUID | None, Query()] = None,
    agency_id: Annotated[uuid.UUID | None, Query()] = None,
    status_value: Annotated[ClaimStatus | None, Query(alias="status")] = None,
) -> list[ClaimResponse]:
    stmt = (
        select(Claim)
        .join(Patient)
        .where(
            Claim.tenant_id == current_user.tenant_id,
            Patient.user_id == current_user.id,
            Patient.id == Claim.patient_id,
        )
    )
    if patient_id:
        stmt = stmt.where(Claim.patient_id == patient_id)
    if agency_id:
        stmt = stmt.where(Claim.agency_id == agency_id)
    if status_value:
        stmt = stmt.where(Claim.status == status_value)
    claims = db.execute(stmt.order_by(Claim.created_at.desc())).scalars().all()
    return [ClaimResponse.model_validate(claim) for claim in claims]


@router.post("", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def create_claim(
    payload: ClaimCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ClaimResponse | JSONResponse:
    patient = _require_patient(db, payload.patient_id, current_user)
    _require_agency(db, payload.agency_id, current_user)
    if payload.claim_number:
        existing = db.execute(
            select(Claim).where(
                Claim.agency_id == payload.agency_id,
                Claim.claim_number == payload.claim_number,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="CLAIM_NUMBER_EXISTS",
                    message="Claim number already exists for agency",
                    details={"claim_number": payload.claim_number},
                ),
            )
    claim = Claim(
        tenant_id=current_user.tenant_id,
        agency_id=payload.agency_id,
        patient_id=patient.id,
        claim_number=payload.claim_number,
        status=payload.status,
        service_from=payload.service_from,
        service_to=payload.service_to,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return ClaimResponse.model_validate(claim)


@router.get("/{claim_id}", response_model=ClaimResponse)
def get_claim(
    claim_id: uuid.UUID,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ClaimResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    return ClaimResponse.model_validate(claim)


@router.patch("/{claim_id}", response_model=ClaimResponse)
def update_claim(
    claim_id: uuid.UUID,
    payload: ClaimUpdateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ClaimResponse | JSONResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    data = payload.model_dump(exclude_unset=True)
    if "agency_id" in data and data["agency_id"] is not None:
        _require_agency(db, data["agency_id"], current_user)
    if "claim_number" in data and data["claim_number"]:
        existing = db.execute(
            select(Claim).where(
                Claim.agency_id == data.get("agency_id", claim.agency_id),
                Claim.claim_number == data["claim_number"],
                Claim.id != claim.id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="CLAIM_NUMBER_EXISTS",
                    message="Claim number already exists for agency",
                    details={"claim_number": data["claim_number"]},
                ),
            )
    for field, value in data.items():
        setattr(claim, field, value)
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return ClaimResponse.model_validate(claim)


@router.post("/{claim_id}/visits", response_model=list[uuid.UUID])
def attach_visits(
    claim_id: uuid.UUID,
    payload: ClaimVisitAttachRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[uuid.UUID] | JSONResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    if not payload.visit_ids:
        return []
    visits = (
        db.execute(
            select(Visit).where(
                Visit.id.in_(payload.visit_ids),
                Visit.tenant_id == current_user.tenant_id,
            )
        )
        .scalars()
        .all()
    )
    visit_by_id = {visit.id: visit for visit in visits}
    missing = [vid for vid in payload.visit_ids if vid not in visit_by_id]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")
    for visit in visits:
        if visit.patient_id != claim.patient_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Visit does not belong to claim patient",
            )
    existing_ids = {visit.id for visit in claim.visits}
    duplicates = [vid for vid in payload.visit_ids if vid in existing_ids]
    if duplicates:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="VISIT_ALREADY_LINKED",
                message="Visit already linked to claim",
                details={"visit_ids": [str(vid) for vid in duplicates]},
            ),
        )
    for visit in visits:
        claim.visits.append(visit)
    db.add(claim)
    db.commit()
    return [visit.id for visit in visits]


@router.post("/{claim_id}/procedures", response_model=list[ClaimProcedureResponse])
def add_procedures(
    claim_id: uuid.UUID,
    payload: ClaimProcedureCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[ClaimProcedureResponse] | JSONResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    if not payload.procedures:
        return []
    procedure_ids = [item.procedure_code_id for item in payload.procedures]
    codes = (
        db.execute(
            select(ProcedureCode).where(
                ProcedureCode.id.in_(procedure_ids),
                ProcedureCode.tenant_id == current_user.tenant_id,
            )
        )
        .scalars()
        .all()
    )
    code_by_id = {code.id: code for code in codes}
    missing = [pid for pid in procedure_ids if pid not in code_by_id]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Procedure code not found",
        )

    responses: list[ClaimProcedureResponse] = []
    for item in payload.procedures:
        existing = db.execute(
            select(ClaimProcedure).where(
                ClaimProcedure.claim_id == claim.id,
                ClaimProcedure.tenant_id == current_user.tenant_id,
                ClaimProcedure.procedure_code_id == item.procedure_code_id,
                ClaimProcedure.modifier == item.modifier,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="PROCEDURE_ALREADY_LINKED",
                    message="Procedure already linked to claim",
                    details={
                        "procedure_code_id": str(item.procedure_code_id),
                        "modifier": item.modifier,
                    },
                ),
            )
        procedure = ClaimProcedure(
            tenant_id=current_user.tenant_id,
            claim_id=claim.id,
            procedure_code_id=item.procedure_code_id,
            units=item.units,
            modifier=item.modifier,
            price=item.price,
        )
        db.add(procedure)
        db.flush()
        db.refresh(procedure)
        responses.append(ClaimProcedureResponse.model_validate(procedure))
    db.commit()
    return responses


@router.get("/{claim_id}/policy-links", response_model=list[ClaimPolicyLinkItem])
def resolve_policy_links(
    claim_id: uuid.UUID,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[ClaimPolicyLinkItem]:
    claim = _get_claim_or_404(db, claim_id, current_user)
    procedures = db.execute(
        select(ClaimProcedure, ProcedureCode, AgencyProcedurePolicyLink)
        .join(ProcedureCode, ClaimProcedure.procedure_code_id == ProcedureCode.id)
        .outerjoin(
            AgencyProcedurePolicyLink,
            (AgencyProcedurePolicyLink.agency_id == claim.agency_id)
            & (AgencyProcedurePolicyLink.procedure_code_id == ProcedureCode.id)
            & (AgencyProcedurePolicyLink.status == PolicyLinkStatus.ACTIVE)
            & (AgencyProcedurePolicyLink.tenant_id == current_user.tenant_id),
        )
        .where(
            ClaimProcedure.claim_id == claim.id,
            ClaimProcedure.tenant_id == current_user.tenant_id,
            ProcedureCode.tenant_id == current_user.tenant_id,
        )
    ).all()
    items: list[ClaimPolicyLinkItem] = []
    for _claim_proc, code, link in procedures:
        summary = ProcedureCodeSummary(
            id=code.id,
            code=code.code,
            title=code.title,
        )
        policy_url = link.policy_url if link else None
        items.append(
            ClaimPolicyLinkItem(
                procedure_code=summary,
                policy_url=policy_url,
                missing_policy_link=policy_url is None,
            )
        )
    return items
