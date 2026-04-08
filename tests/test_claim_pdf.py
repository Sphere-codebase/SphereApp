import os
import tempfile

import pytest

from app.pdf.claim_pdf import (
    ClaimData,
    PatientData,
    PhysicianSupplierData,
    BillingData,
    ServiceLine,
    generate_pdf_bytes,
    save_pdf,
)


@pytest.fixture
def sample_claim():
    patient = PatientData(
        last_name="Doe",
        first_name="John",
        suffix=None,
        middle=None,
        is_employment=False,
        is_auto=False,
        is_other=False,
        auto_incident_state=None,
        line_1="Street 1",
        line_2=None,
        city="City",
        state="ST",
        zip_code="12345",
        dob="1990-01-01",
        sex="M",
        patient_relationship="Self",
        patient_signature="Signed",
        account_number="ACC123",
    )

    physician = PhysicianSupplierData(
        last_name="House",
        first_name="Gregory",
        suffix=None,
        middle=None,
        physician_supplier_signature=True,
        submitter_type="doctor",
        phone_number=None,
        fax=None,
        email=None,
        etin=None,
    )

    billing = BillingData(
        last_name="Clinic",
        first_name="General",
        suffix=None,
        middle=None,
        line_1="Billing St",
        line_2=None,
        city="Town",
        state="TS",
        zip_code="54321",
        provider_type="facility",
        phone_number=None,
        npi="999999",
        other_ids=[],
    )

    service_line = ServiceLine(
        note=["note1"],
        dos="2024-01-01",
        pos=None,
        emg=None,
        procedures="PROC",
        diagnosis="DX",
        charge="100",
        days_units="1",
        epsdt=None,
        provider_id=["PID"],
    )

    return ClaimData(
        insurance_company="InsureCo",
        insurance_type="Private",
        identifier_type="TypeA",
        edi_mode="Test",
        patient=patient,
        claim_codes=["A"],
        other_claim_id=[],
        illness_date=None,
        other_dates=[],
        not_working_dates=[],
        provider=None,
        other_id_npi=[],
        hospitalization_dates=[],
        additional_claim_info=[],
        outside_lab=[],
        diagnosis=["D1"],
        resubmission_code=None,
        prior_authorization_number=[],
        service_lines=[service_line],
        federal_tax_id="FT123",
        federal_number_type="SSN",
        accept_assignment="Yes",
        total_charge="100",
        amount_paid=None,
        physician_supplier=physician,
        facility=None,
        billing_info=billing,
    )


def test_pdf_generation_does_not_fail(sample_claim):
    pdf_bytes = generate_pdf_bytes(sample_claim)
    assert pdf_bytes is not None


def test_pdf_starts_with_signature(sample_claim):
    pdf_bytes = generate_pdf_bytes(sample_claim)
    assert pdf_bytes.startswith(b"%PDF")


def test_file_saved_and_not_empty(sample_claim):
    pdf_bytes = generate_pdf_bytes(sample_claim)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        path = tmp.name

    try:
        save_pdf(pdf_bytes, path)

        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    finally:
        if os.path.exists(path):
            os.remove(path)
