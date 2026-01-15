"""Admin claim read-only endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import (
    Claim,
    ClaimDiagnosisCode,
    ClaimProcedureFact,
    DiagnosisCode,
    InsuranceCompany,
    McpCode,
    Patient,
    User,
)
from app.db.session import get_db
from app.schemas.admin_dashboard import (
    AdminClaimDetailResponse,
    AdminClaimProcedureFactResponse,
    AdminClaimSummary,
    AdminDiagnosisCodeSummary,
    AdminInsuranceCompanySummary,
    AdminPatientSummary,
    McpCodeSummary,
)

router = APIRouter(prefix="/api/admin/claims", tags=["admin_claims"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[AdminClaimSummary])
def list_claims(
    db: DbSessionDep,
    current_user: AdminUserDep,
    patient_id: Annotated[int | None, Query()] = None,
    insurance_company_id: Annotated[int | None, Query()] = None,
    status_value: Annotated[str | None, Query(alias="status")] = None,
    service_from: Annotated[date | None, Query()] = None,
    service_to: Annotated[date | None, Query()] = None,
) -> list[AdminClaimSummary]:
    stmt = (
        select(Claim, Patient, InsuranceCompany)
        .join(Patient, Claim.patient_id == Patient.id)
        .join(InsuranceCompany, Claim.insurance_company_id == InsuranceCompany.id)
    )
    if patient_id:
        stmt = stmt.where(Claim.patient_id == patient_id)
    if insurance_company_id:
        stmt = stmt.where(Claim.insurance_company_id == insurance_company_id)
    if status_value:
        stmt = stmt.where(Claim.claim_status == status_value)
    if service_from:
        stmt = stmt.where(Claim.service_date >= service_from)
    if service_to:
        stmt = stmt.where(Claim.service_date <= service_to)
    rows = db.execute(stmt.order_by(Claim.created_at.desc())).all()
    summaries: list[AdminClaimSummary] = []
    for claim, patient, company in rows:
        patient_name = " ".join(
            part for part in [patient.first_name or "", patient.last_name or ""] if part
        ).strip()
        summaries.append(
            AdminClaimSummary(
                id=claim.id,
                patient_id=claim.patient_id,
                patient_name=patient_name,
                doctor_id=claim.doctor_id,
                insurance_company_id=claim.insurance_company_id,
                insurance_company_name=company.name if company else None,
                claim_number=claim.claim_number,
                claim_status=claim.claim_status,
                service_date=claim.service_date,
                claim_date=claim.claim_date,
                billed_amount_total=float(claim.billed_amount_total)
                if claim.billed_amount_total is not None
                else None,
                allowed_amount_total=float(claim.allowed_amount_total)
                if claim.allowed_amount_total is not None
                else None,
                coinsurance_amount_total=float(claim.coinsurance_amount_total)
                if claim.coinsurance_amount_total is not None
                else None,
                copay_amount_total=float(claim.copay_amount_total)
                if claim.copay_amount_total is not None
                else None,
                deductible_amount_total=float(claim.deductible_amount_total)
                if claim.deductible_amount_total is not None
                else None,
                created_at=claim.created_at,
            )
        )
    return summaries


@router.get("/{claim_id}", response_model=AdminClaimDetailResponse)
def get_claim(
    claim_id: int,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AdminClaimDetailResponse:
    claim_row = db.execute(
        select(Claim, Patient, InsuranceCompany)
        .join(Patient, Claim.patient_id == Patient.id)
        .join(InsuranceCompany, Claim.insurance_company_id == InsuranceCompany.id)
        .where(
            Claim.id == claim_id,
        )
    ).all()
    if not claim_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    claim, patient, company = claim_row[0]

    procedure_rows = db.execute(
        select(ClaimProcedureFact, McpCode)
        .join(McpCode, ClaimProcedureFact.mcp_code == McpCode.code)
        .where(ClaimProcedureFact.claim_id == claim.id)
        .order_by(ClaimProcedureFact.created_at.asc())
    ).all()
    procedures: list[AdminClaimProcedureFactResponse] = []
    for procedure, code in procedure_rows:
        procedures.append(
            AdminClaimProcedureFactResponse(
                id=procedure.id,
                mcp_code=McpCodeSummary(code=code.code, description=code.description),
                service_date=procedure.service_date,
                units=float(procedure.units) if procedure.units is not None else None,
                modifier=procedure.modifier,
                billed_amount=float(procedure.billed_amount)
                if procedure.billed_amount is not None
                else None,
                allowed_amount=float(procedure.allowed_amount)
                if procedure.allowed_amount is not None
                else None,
                coinsurance_amount=float(procedure.coinsurance_amount)
                if procedure.coinsurance_amount is not None
                else None,
                copay_amount=float(procedure.copay_amount)
                if procedure.copay_amount is not None
                else None,
                deductible_amount=float(procedure.deductible_amount)
                if procedure.deductible_amount is not None
                else None,
                paid_amount=float(procedure.paid_amount)
                if procedure.paid_amount is not None
                else None,
                paid_at=procedure.paid_at,
                created_at=procedure.created_at,
            )
        )

    diagnoses = (
        db.execute(
            select(DiagnosisCode)
            .join(ClaimDiagnosisCode, ClaimDiagnosisCode.diagnosis_code == DiagnosisCode.code)
            .where(
                ClaimDiagnosisCode.claim_id == claim.id,
            )
            .order_by(DiagnosisCode.code.asc())
        )
        .scalars()
        .all()
    )

    return AdminClaimDetailResponse(
        id=claim.id,
        patient=AdminPatientSummary.model_validate(patient),
        insurance_company=AdminInsuranceCompanySummary.model_validate(company) if company else None,
        claim_number=claim.claim_number,
        claim_status=claim.claim_status,
        service_date=claim.service_date,
        claim_date=claim.claim_date,
        billed_amount_total=float(claim.billed_amount_total)
        if claim.billed_amount_total is not None
        else None,
        allowed_amount_total=float(claim.allowed_amount_total)
        if claim.allowed_amount_total is not None
        else None,
        coinsurance_amount_total=float(claim.coinsurance_amount_total)
        if claim.coinsurance_amount_total is not None
        else None,
        copay_amount_total=float(claim.copay_amount_total)
        if claim.copay_amount_total is not None
        else None,
        deductible_amount_total=float(claim.deductible_amount_total)
        if claim.deductible_amount_total is not None
        else None,
        created_at=claim.created_at,
        procedures=procedures,
        diagnoses=[AdminDiagnosisCodeSummary.model_validate(item) for item in diagnoses],
    )
