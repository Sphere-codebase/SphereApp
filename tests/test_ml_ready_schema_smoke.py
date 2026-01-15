import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.models import (
    Claim,
    ClaimDiagnosis,
    ClaimProcedure,
    ClaimStatus,
    Diagnosis,
    Patient,
    ProcedureCode,
    Tenant,
    User,
)


def _seed_claim_context(
    db_session: Session,
) -> tuple[Tenant, Claim, ProcedureCode, Diagnosis]:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Smoke")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    patient = Patient(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        first_name="Jane",
        last_name="Doe",
        full_name="Jane Doe",
    )
    claim = Claim(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        patient_id=patient.id,
        status=ClaimStatus.DRAFT,
    )
    code = ProcedureCode(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        code="99213",
        title="Office Visit",
    )
    diagnosis = Diagnosis(id=uuid.uuid4(), tenant_id=tenant.id, code="A00", title="Cholera")
    db_session.add_all([tenant, user, patient, claim, code, diagnosis])
    db_session.commit()
    return tenant, claim, code, diagnosis


def test_ml_ready_tables_and_columns(db_session: Session) -> None:
    inspector = inspect(db_session.get_bind())
    tables = set(inspector.get_table_names())
    assert "claim_diagnoses" in tables
    assert "claim_procedure_payments" in tables
    assert "procedure_price_by_agency" in tables

    claims_columns = {column["name"] for column in inspector.get_columns("claims")}
    for column in {
        "received_at",
        "finalized_at",
        "billed_total_cents",
        "allowed_total_cents",
        "paid_total_cents",
        "patient_responsibility_cents",
    }:
        assert column in claims_columns

    claim_procedures_columns = {
        column["name"] for column in inspector.get_columns("claim_procedures")
    }
    for column in {
        "billed_amount_cents",
        "allowed_amount_cents",
        "copay_amount_cents",
        "deductible_amount_cents",
        "paid_amount_cents",
        "line_number",
    }:
        assert column in claim_procedures_columns


def test_claim_procedure_units_constraint(db_session: Session) -> None:
    tenant, claim, code, _diagnosis = _seed_claim_context(db_session)
    invalid_units = ClaimProcedure(
        tenant_id=tenant.id,
        claim_id=claim.id,
        procedure_code_id=code.id,
        units=0,
    )
    db_session.add(invalid_units)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_claim_diagnoses_duplicate_constraint(db_session: Session) -> None:
    tenant, claim, _code, diagnosis = _seed_claim_context(db_session)
    link = ClaimDiagnosis(
        tenant_id=tenant.id,
        claim_id=claim.id,
        diagnosis_id=diagnosis.id,
    )
    db_session.add(link)
    db_session.commit()
    db_session.expunge(link)

    duplicate = ClaimDiagnosis(
        tenant_id=tenant.id,
        claim_id=claim.id,
        diagnosis_id=diagnosis.id,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
