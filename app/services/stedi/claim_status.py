"""Claim status payload mapping for Stedi."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Claim, ClaimProcedureFact, Clinic, PatientInsurancePolicy


@dataclass(frozen=True)
class StediPayloadValidationError:
    field: str
    message: str


@dataclass(frozen=True)
class StediClaimStatusPayload:
    payload: dict[str, Any]
    request_summary: dict[str, Any]


def build_claim_status_payload(
    db: Session,
    claim: Claim,
    settings: Settings,
) -> StediClaimStatusPayload | list[StediPayloadValidationError]:
    missing: list[StediPayloadValidationError] = []
    patient = claim.patient
    payer = claim.insurance_company
    clinic = db.execute(select(Clinic).where(Clinic.id == claim.clinic_id)).scalar_one_or_none()
    policy = db.execute(
        select(PatientInsurancePolicy)
        .where(
            PatientInsurancePolicy.patient_id == claim.patient_id,
            PatientInsurancePolicy.insurance_company_id == claim.insurance_company_id,
        )
        .order_by(PatientInsurancePolicy.priority.asc(), PatientInsurancePolicy.created_at.desc())
    ).scalar_one_or_none()

    member_id = _clean(getattr(policy, "member_id", None))
    trading_partner_service_id = _clean(getattr(payer, "stedi_trading_partner_service_id", None))
    service_dates = _service_dates(db, claim)
    provider = _billing_provider(clinic, settings)

    if not trading_partner_service_id:
        missing.append(
            StediPayloadValidationError(
                field="insurance_company.stedi_trading_partner_service_id",
                message="Set the payer Stedi trading partner service ID.",
            )
        )
    if not member_id:
        missing.append(
            StediPayloadValidationError(
                field="patient_insurance_policy.member_id",
                message="Set the patient's member ID for this payer.",
            )
        )
    if not patient.first_name:
        missing.append(
            StediPayloadValidationError(
                field="patient.first_name",
                message="Set the patient's first name.",
            )
        )
    if not patient.last_name:
        missing.append(
            StediPayloadValidationError(
                field="patient.last_name",
                message="Set the patient's last name.",
            )
        )
    if not patient.date_of_birth:
        missing.append(
            StediPayloadValidationError(
                field="patient.date_of_birth",
                message="Set the patient's date of birth.",
            )
        )
    if service_dates is None:
        missing.append(
            StediPayloadValidationError(
                field="claim.service_date",
                message="Set the claim service date or line service dates.",
            )
        )
    if provider is None:
        missing.append(
            StediPayloadValidationError(
                field="clinic.billing_provider",
                message=(
                    "Set clinic billing provider organization name and NPI or TIN, "
                    "or configure STEDI_PROVIDER_* fallbacks."
                ),
            )
        )
    if missing:
        return missing

    assert service_dates is not None
    assert provider is not None
    assert member_id is not None
    assert trading_partner_service_id is not None
    assert patient.date_of_birth is not None

    encounter: dict[str, Any] = {
        "beginningDateOfService": _stedi_date(service_dates[0]),
        "endDateOfService": _stedi_date(service_dates[1]),
    }
    submitted_amount = _decimal_or_none(claim.billed_amount_total)
    if submitted_amount is not None:
        encounter["submittedAmount"] = _decimal_text(submitted_amount)
    account_number = _clean(patient.chart_number) or _clean(claim.claim_number)
    if account_number:
        encounter["patientAccountNumber"] = account_number

    subscriber: dict[str, Any] = {
        "dateOfBirth": _stedi_date(patient.date_of_birth),
        "firstName": patient.first_name,
        "lastName": patient.last_name,
        "memberId": member_id,
    }
    gender = _stedi_gender(patient.gender)
    if gender:
        subscriber["gender"] = gender

    payload = {
        "encounter": encounter,
        "providers": [provider],
        "subscriber": subscriber,
        "tradingPartnerServiceId": trading_partner_service_id,
    }
    return StediClaimStatusPayload(
        payload=payload,
        request_summary={
            "has_patient_account_number": bool(account_number),
            "has_submitted_amount": submitted_amount is not None,
            "provider_type": "BillingProvider",
            "provider_identifier": _provider_identifier_summary(provider),
            "service_date_source": "claim" if claim.service_date else "procedure_facts",
            "trading_partner_service_id_present": True,
        },
    )


def _service_dates(db: Session, claim: Claim) -> tuple[date, date] | None:
    if claim.service_date is not None:
        return claim.service_date, claim.service_date
    dates = (
        db.execute(
            select(ClaimProcedureFact.service_date)
            .where(
                ClaimProcedureFact.claim_id == claim.id,
                ClaimProcedureFact.service_date.is_not(None),
            )
            .order_by(ClaimProcedureFact.service_date.asc())
        )
        .scalars()
        .all()
    )
    if not dates:
        return None
    return dates[0], dates[-1]


def _billing_provider(clinic: Clinic | None, settings: Settings) -> dict[str, Any] | None:
    organization_name = _clean(
        getattr(clinic, "billing_provider_organization_name", None)
    ) or _clean(settings.stedi_provider_organization_name)
    npi = _clean(getattr(clinic, "billing_provider_npi", None)) or _clean(
        settings.stedi_provider_npi
    )
    tax_id = _clean(getattr(clinic, "billing_provider_tax_id", None)) or _clean(
        settings.stedi_provider_tax_id
    )
    if not organization_name or not (npi or tax_id):
        return None
    provider = {
        "organizationName": organization_name,
        "providerType": "BillingProvider",
    }
    if npi:
        provider["npi"] = npi
    elif tax_id:
        provider["taxId"] = tax_id
    return provider


def _provider_identifier_summary(provider: dict[str, Any]) -> str:
    if provider.get("npi"):
        return "npi"
    if provider.get("taxId"):
        return "taxId"
    return "none"


def _stedi_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def _stedi_gender(value: str | None) -> str | None:
    text = _clean(value)
    if not text:
        return None
    first = text[:1].upper()
    return first if first in {"M", "F"} else None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _decimal_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
