"""Claim to PDF Parser"""

from __future__ import annotations

import os
from dataclasses import is_dataclass, asdict, dataclass
from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListItem, ListFlowable
from reportlab.lib.styles import getSampleStyleSheet

@dataclass
class PersonBaseData:
    last_name: str
    first_name: str
    suffix: str | None
    middle: str | None

@dataclass
class PatientCondition:
    is_employment: bool
    is_auto: bool
    is_other: bool
    auto_incident_state: str | None

@dataclass
class EntityAddress:
    line_1: str
    line_2: str | None
    city: str
    state: str
    zip_code: str

@dataclass
class PatientData(PersonBaseData, PatientCondition, EntityAddress):
    dob: str
    sex: str
    patient_relationship: str
    patient_signature: str
    account_number: str

@dataclass
class InsuredData(PersonBaseData, EntityAddress):
    insurred_id_number: str
    responsibility_level: str
    insured_policy_or_feca: str | None
    dob: str | None
    sex: str | None
    insured_signature: str

@dataclass
class OtherClaim:
    qualifier: str
    value: str

@dataclass
class QualifierValueOrDate:
    qualifier: str
    value: str

@dataclass
class DatePeriod:
    from_date: str
    to_date: str

@dataclass
class ProviderInfo(PersonBaseData):
    qualifier: str

@dataclass
class ServiceLine:
    note: list[str]
    dos: str
    pos: str | None
    emg: str | None
    procedures: str
    diagnosis: str
    charge: str
    days_units: str
    epsdt: str | None
    provider_id: list[str]

@dataclass
class PhysicianSupplierData(PersonBaseData):
    physician_supplier_signature: bool
    submitter_type: str
    phone_number: str | None
    fax: str | None
    email: str | None
    etin: str | None

@dataclass
class FacilityData(EntityAddress):
    name: str
    npi: str
    other_ids: list[QualifierValueOrDate]

@dataclass
class BillingData(PersonBaseData, EntityAddress):
    provider_type: str
    phone_number: str | None
    npi: str
    other_ids: list[QualifierValueOrDate]

@dataclass
class ClaimData:
    insurance_company: str
    insurance_type: str
    identifier_type: str
    edi_mode: str
    patient: PatientData
    claim_codes: list[str]
    other_claim_id: list[OtherClaim]
    illness_date: QualifierValueOrDate | None
    other_dates: list[QualifierValueOrDate]
    not_working_dates: list[DatePeriod]
    provider: ProviderInfo | None
    other_id_npi: list[QualifierValueOrDate]
    hospitalization_dates: list[DatePeriod]
    additional_claim_info: list[QualifierValueOrDate]
    outside_lab: list[str]
    diagnosis: list[str]
    resubmission_code: QualifierValueOrDate | None
    prior_authorization_number: list[QualifierValueOrDate]
    service_lines: list[ServiceLine]
    federal_tax_id: str
    federal_number_type: str
    accept_assignment: str
    total_charge: str
    amount_paid: str | None
    physician_supplier: PhysicianSupplierData
    facility: FacilityData | None
    billing_info: BillingData

def _is_empty(value: Any) -> bool:
    """Return True if value should be skipped in PDF."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def _normalize(value: Any) -> Any:
    """Convert dataclasses to dicts recursively."""
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def _format_key(key: str) -> str:
    """Convert snake_case to Title Case."""
    return key.replace("_", " ").title()

def generate_pdf_bytes(claim) -> bytes:
    if claim is None:
        raise ValueError("ClaimData cannot be None")

    def normalize(value: Any) -> Any:
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, list):
            return [normalize(v) for v in value]
        return value

    def is_empty(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        if isinstance(value, (list, dict)) and not value:
            return True
        return False

    def format_key(key: str) -> str:
        return key.replace("_", " ").title()

    data = normalize(claim)

    styles = getSampleStyleSheet()
    elements = []

    def render(obj: Any, indent: int = 0):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if is_empty(value):
                    continue

                title = format_key(key)

                # CASE 1 — scalar value
                if not isinstance(value, (dict, list)):
                    elements.append(
                        Paragraph(
                            "&nbsp;" * indent * 4 + f"<b>{title}:</b> {value}",
                            styles["Normal"],
                        )
                    )
                    elements.append(Spacer(1, 4))

                # CASE 2 — nested structure
                else:
                    elements.append(
                        Paragraph(
                            "&nbsp;" * indent * 4 + f"<b>{title}</b>",
                            styles["Normal"],
                        )
                    )
                    elements.append(Spacer(1, 4))
                    render(value, indent + 1)

        elif isinstance(obj, list):
            items = []

            for item in obj:
                if is_empty(item):
                    continue

                if isinstance(item, (dict, list)):
                    sub_before = len(elements)
                    render(item, indent + 1)
                    sub_content = elements[sub_before:]
                    items.append(ListItem(sub_content))
                else:
                    items.append(
                        ListItem(
                            Paragraph(str(item), styles["Normal"])
                        )
                    )

            if items:
                elements.append(ListFlowable(items, bulletType="bullet"))
                elements.append(Spacer(1, 6))

        else:
            elements.append(
                Paragraph("&nbsp;" * indent * 4 + str(obj), styles["Normal"])
            )
            elements.append(Spacer(1, 4))

    render(data)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError("Invalid PDF generated")

    return pdf_bytes


# ---------- File Writer ----------

def save_pdf(pdf_bytes: bytes, output_path: str) -> None:
    """
    Save PDF bytes to disk safely.
    """

    if not pdf_bytes:
        raise ValueError("PDF bytes are empty")

    if not output_path.lower().endswith(".pdf"):
        raise ValueError("Output path must end with .pdf")

    directory = os.path.dirname(output_path)

    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    try:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
    except OSError as exc:
        raise OSError(f"Failed to write PDF file: {exc}") from exc