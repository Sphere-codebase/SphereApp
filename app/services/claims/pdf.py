"""Claim PDF generation helpers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Claim, ClaimDiagnosisCode, ClaimMcpCode, DiagnosisCode, McpCode
from app.pdf.claim_pdf import (
    BillingData,
    ClaimData,
    PatientData,
    PhysicianSupplierData,
    ServiceLine,
)


def _date_or_empty(value: date | None) -> str:
    return value.isoformat() if value else ""


def build_claim_pdf_data(db: Session, claim: Claim) -> ClaimData:
    patient = claim.patient
    insurance_company = claim.insurance_company

    mcp_rows = db.execute(
        select(ClaimMcpCode, McpCode)
        .join(McpCode, ClaimMcpCode.mcp_code == McpCode.code)
        .where(ClaimMcpCode.claim_id == claim.id)
        .order_by(McpCode.code.asc())
    ).all()
    mcp_codes = [code.code for _link, code in mcp_rows]

    diagnosis_rows = db.execute(
        select(ClaimDiagnosisCode, DiagnosisCode)
        .join(DiagnosisCode, ClaimDiagnosisCode.diagnosis_code == DiagnosisCode.code)
        .where(ClaimDiagnosisCode.claim_id == claim.id)
        .order_by(DiagnosisCode.code.asc())
    ).all()
    diagnosis_codes = [code.code for _link, code in diagnosis_rows]

    diagnosis_primary = diagnosis_codes[0] if diagnosis_codes else ""
    service_date = _date_or_empty(claim.service_date)
    total_charge = str(claim.billed_amount_total or 0)

    service_lines = [
        ServiceLine(
            note=[],
            dos=service_date,
            pos=None,
            emg=None,
            procedures=code,
            diagnosis=diagnosis_primary,
            charge=total_charge,
            days_units="1",
            epsdt=None,
            provider_id=[],
        )
        for code in mcp_codes
    ]

    patient_data = PatientData(
        last_name=patient.last_name or "",
        first_name=patient.first_name or "",
        suffix=None,
        middle=None,
        dob=_date_or_empty(patient.date_of_birth),
        sex=patient.gender or "",
        patient_relationship="",
        patient_signature="",
        account_number=patient.chart_number or "",
        is_employment=False,
        is_auto=False,
        is_other=False,
        auto_incident_state=None,
        line_1="",
        line_2=None,
        city="",
        state="",
        zip_code="",
    )

    billing_info = BillingData(
        last_name="",
        first_name="",
        suffix=None,
        middle=None,
        provider_type="",
        phone_number=None,
        npi="",
        other_ids=[],
        line_1="",
        line_2=None,
        city="",
        state="",
        zip_code="",
    )

    physician_supplier = PhysicianSupplierData(
        last_name="",
        first_name="",
        suffix=None,
        middle=None,
        physician_supplier_signature=False,
        submitter_type="",
        phone_number=None,
        fax=None,
        email=None,
        etin=None,
    )

    return ClaimData(
        insurance_company=insurance_company.name if insurance_company else "",
        insurance_type="",
        identifier_type="",
        edi_mode="",
        patient=patient_data,
        claim_codes=[],
        other_claim_id=[],
        illness_date=None,
        other_dates=[],
        not_working_dates=[],
        provider=None,
        other_id_npi=[],
        hospitalization_dates=[],
        additional_claim_info=[],
        outside_lab=[],
        diagnosis=diagnosis_codes,
        resubmission_code=None,
        prior_authorization_number=[],
        service_lines=service_lines,
        federal_tax_id="",
        federal_number_type="",
        accept_assignment="",
        total_charge=total_charge,
        amount_paid=None,
        physician_supplier=physician_supplier,
        facility=None,
        billing_info=billing_info,
    )
