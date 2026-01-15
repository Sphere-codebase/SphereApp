"""Admin claim read-only endpoints."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import (
    Agency,
    Claim,
    ClaimDiagnosis,
    ClaimProcedure,
    ClaimProcedurePayment,
    Diagnosis,
    Patient,
    ProcedureCode,
    User,
)
from app.db.models.enums import ClaimStatus
from app.db.session import get_db
from app.schemas.admin_dashboard import (
    AdminAgencySummary,
    AdminClaimDetailResponse,
    AdminClaimProcedurePaymentResponse,
    AdminClaimProcedureResponse,
    AdminClaimSummary,
    AdminDiagnosisSummary,
    AdminPatientSummary,
    ProcedureCodeSummary,
)

router = APIRouter(prefix="/api/admin/claims", tags=["admin_claims"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[AdminClaimSummary])
def list_claims(
    db: DbSessionDep,
    current_user: AdminUserDep,
    patient_id: Annotated[uuid.UUID | None, Query()] = None,
    agency_id: Annotated[uuid.UUID | None, Query()] = None,
    status_value: Annotated[ClaimStatus | None, Query(alias="status")] = None,
    service_from: Annotated[date | None, Query()] = None,
    service_to: Annotated[date | None, Query()] = None,
) -> list[AdminClaimSummary]:
    stmt = (
        select(Claim, Patient, Agency)
        .join(Patient, Claim.patient_id == Patient.id)
        .outerjoin(
            Agency,
            (Claim.agency_id == Agency.id) & (Agency.tenant_id == current_user.tenant_id),
        )
        .where(
            Claim.tenant_id == current_user.tenant_id,
            Patient.tenant_id == current_user.tenant_id,
        )
    )
    if patient_id:
        stmt = stmt.where(Claim.patient_id == patient_id)
    if agency_id:
        stmt = stmt.where(Claim.agency_id == agency_id)
    if status_value:
        stmt = stmt.where(Claim.status == status_value)
    if service_from:
        stmt = stmt.where(Claim.service_from >= service_from)
    if service_to:
        stmt = stmt.where(Claim.service_to <= service_to)
    rows = db.execute(stmt.order_by(Claim.created_at.desc())).all()
    summaries: list[AdminClaimSummary] = []
    for claim, patient, agency in rows:
        summaries.append(
            AdminClaimSummary(
                id=claim.id,
                patient_id=claim.patient_id,
                patient_name=patient.full_name,
                patient_user_id=patient.user_id,
                agency_id=claim.agency_id,
                agency_name=agency.name if agency else None,
                claim_number=claim.claim_number,
                status=claim.status,
                service_from=claim.service_from,
                service_to=claim.service_to,
                received_at=claim.received_at,
                finalized_at=claim.finalized_at,
                billed_total_cents=claim.billed_total_cents,
                allowed_total_cents=claim.allowed_total_cents,
                paid_total_cents=claim.paid_total_cents,
                patient_responsibility_cents=claim.patient_responsibility_cents,
                created_at=claim.created_at,
                updated_at=claim.updated_at,
            )
        )
    return summaries


@router.get("/{claim_id}", response_model=AdminClaimDetailResponse)
def get_claim(
    claim_id: uuid.UUID,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AdminClaimDetailResponse:
    claim_row = (
        db.execute(
            select(Claim, Patient, Agency)
            .join(Patient, Claim.patient_id == Patient.id)
            .outerjoin(
                Agency,
                (Claim.agency_id == Agency.id)
                & (Agency.tenant_id == current_user.tenant_id),
            )
            .where(
                Claim.id == claim_id,
                Claim.tenant_id == current_user.tenant_id,
                Patient.tenant_id == current_user.tenant_id,
            )
        )
        .all()
    )
    if not claim_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    claim, patient, agency = claim_row[0]

    procedure_rows = db.execute(
        select(ClaimProcedure, ProcedureCode)
        .join(ProcedureCode, ClaimProcedure.procedure_code_id == ProcedureCode.id)
        .where(
            ClaimProcedure.claim_id == claim.id,
            ClaimProcedure.tenant_id == current_user.tenant_id,
            ProcedureCode.tenant_id == current_user.tenant_id,
        )
        .order_by(ClaimProcedure.created_at.asc())
    ).all()
    procedure_ids = [proc.id for proc, _code in procedure_rows]
    payments_by_proc: dict[uuid.UUID, list[AdminClaimProcedurePaymentResponse]] = {}
    if procedure_ids:
        payments = (
            db.execute(
                select(ClaimProcedurePayment).where(
                    ClaimProcedurePayment.claim_procedure_id.in_(procedure_ids),
                    ClaimProcedurePayment.tenant_id == current_user.tenant_id,
                )
            )
            .scalars()
            .all()
        )
        for payment in payments:
            payments_by_proc.setdefault(payment.claim_procedure_id, []).append(
                AdminClaimProcedurePaymentResponse.model_validate(payment)
            )

    procedures: list[AdminClaimProcedureResponse] = []
    for procedure, code in procedure_rows:
        procedures.append(
            AdminClaimProcedureResponse(
                id=procedure.id,
                procedure_code=ProcedureCodeSummary(
                    id=code.id,
                    code=code.code,
                    title=code.title,
                ),
                units=procedure.units,
                modifier=procedure.modifier,
                price=float(procedure.price) if procedure.price is not None else None,
                billed_amount_cents=procedure.billed_amount_cents,
                allowed_amount_cents=procedure.allowed_amount_cents,
                coinsurance_amount_cents=procedure.coinsurance_amount_cents,
                copay_amount_cents=procedure.copay_amount_cents,
                deductible_amount_cents=procedure.deductible_amount_cents,
                paid_amount_cents=procedure.paid_amount_cents,
                denial_reason_code=procedure.denial_reason_code,
                line_number=procedure.line_number,
                created_at=procedure.created_at,
                updated_at=procedure.updated_at,
                payments=payments_by_proc.get(procedure.id, []),
            )
        )

    diagnoses = (
        db.execute(
            select(Diagnosis)
            .join(ClaimDiagnosis, ClaimDiagnosis.diagnosis_id == Diagnosis.id)
            .where(
                ClaimDiagnosis.claim_id == claim.id,
                ClaimDiagnosis.tenant_id == current_user.tenant_id,
                Diagnosis.tenant_id == current_user.tenant_id,
            )
            .order_by(Diagnosis.code.asc())
        )
        .scalars()
        .all()
    )

    return AdminClaimDetailResponse(
        id=claim.id,
        patient=AdminPatientSummary.model_validate(patient),
        agency=AdminAgencySummary.model_validate(agency) if agency else None,
        claim_number=claim.claim_number,
        status=claim.status,
        service_from=claim.service_from,
        service_to=claim.service_to,
        received_at=claim.received_at,
        finalized_at=claim.finalized_at,
        billed_total_cents=claim.billed_total_cents,
        allowed_total_cents=claim.allowed_total_cents,
        paid_total_cents=claim.paid_total_cents,
        patient_responsibility_cents=claim.patient_responsibility_cents,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
        procedures=procedures,
        diagnoses=[AdminDiagnosisSummary.model_validate(item) for item in diagnoses],
    )
