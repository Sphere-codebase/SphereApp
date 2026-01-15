import uuid

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Agency,
    Claim,
    ClaimDiagnosis,
    ClaimProcedure,
    ClaimStatus,
    Diagnosis,
    Patient,
    ProcedureCode,
    ProcedurePriceByAgency,
    Tenant,
    User,
)
from app.services.procedure_price_stats import _recompute_with_session


def _seed_claim_context(
    db_session: Session,
) -> tuple[Tenant, Claim, ProcedureCode, Diagnosis, Agency]:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant ML")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password="hashed",
        is_active=True,
    )
    agency = Agency(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Agency ML",
        slug="agency-ml",
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
        agency_id=agency.id,
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
    db_session.add_all([tenant, user, agency, patient, claim, code, diagnosis])
    db_session.commit()
    return tenant, claim, code, diagnosis, agency


def test_ml_ready_schema_tables_and_columns(db_session: Session) -> None:
    inspector = inspect(db_session.get_bind())
    tables = set(inspector.get_table_names())
    for table in {
        "claim_diagnoses",
        "claim_procedure_payments",
        "procedure_price_by_agency",
    }:
        assert table in tables

    claim_columns = {column["name"] for column in inspector.get_columns("claims")}
    for column in {
        "received_at",
        "finalized_at",
        "billed_total_cents",
        "allowed_total_cents",
        "paid_total_cents",
        "patient_responsibility_cents",
    }:
        assert column in claim_columns

    claim_procedure_columns = {
        column["name"] for column in inspector.get_columns("claim_procedures")
    }
    for column in {
        "tenant_id",
        "billed_amount_cents",
        "allowed_amount_cents",
        "coinsurance_amount_cents",
        "copay_amount_cents",
        "deductible_amount_cents",
        "paid_amount_cents",
        "denial_reason_code",
        "line_number",
    }:
        assert column in claim_procedure_columns

    claim_indexes = {index["name"] for index in inspector.get_indexes("claims")}
    assert "ix_claims_tenant_patient" in claim_indexes
    assert "ix_claims_tenant_agency" in claim_indexes
    assert "ix_claims_tenant_status" in claim_indexes


def test_claim_diagnoses_unique_constraint(db_session: Session) -> None:
    tenant, claim, _code, diagnosis, _agency = _seed_claim_context(db_session)
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


def test_claim_procedure_units_constraint(db_session: Session) -> None:
    tenant, claim, code, _diagnosis, _agency = _seed_claim_context(db_session)
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


def test_claim_procedure_amount_constraints(db_session: Session) -> None:
    tenant, claim, code, _diagnosis, _agency = _seed_claim_context(db_session)
    invalid_amount = ClaimProcedure(
        tenant_id=tenant.id,
        claim_id=claim.id,
        procedure_code_id=code.id,
        units=1,
        billed_amount_cents=-25,
    )
    db_session.add(invalid_amount)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_recompute_procedure_price_stats(db_session: Session) -> None:
    tenant, claim, code, _diagnosis, agency = _seed_claim_context(db_session)
    second_claim = Claim(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        agency_id=agency.id,
        patient_id=claim.patient_id,
        status=ClaimStatus.DRAFT,
    )
    db_session.add(second_claim)
    db_session.commit()

    db_session.add_all(
        [
            ClaimProcedure(
                tenant_id=tenant.id,
                claim_id=claim.id,
                procedure_code_id=code.id,
                units=1,
                paid_amount_cents=100,
            ),
            ClaimProcedure(
                tenant_id=tenant.id,
                claim_id=second_claim.id,
                procedure_code_id=code.id,
                units=1,
                modifier="A",
                paid_amount_cents=200,
            ),
            ClaimProcedure(
                tenant_id=tenant.id,
                claim_id=second_claim.id,
                procedure_code_id=code.id,
                units=1,
                modifier="B",
                paid_amount_cents=300,
            ),
        ]
    )
    db_session.commit()

    _recompute_with_session(db_session, tenant.id, agency.id, code.id)

    stats = db_session.execute(
        select(ProcedurePriceByAgency).where(
            ProcedurePriceByAgency.tenant_id == tenant.id,
            ProcedurePriceByAgency.agency_id == agency.id,
            ProcedurePriceByAgency.procedure_code_id == code.id,
        )
    ).scalar_one()

    assert stats.claims_count == 3
    assert stats.min_paid_cents == 100
    assert stats.max_paid_cents == 300
    assert stats.avg_paid_cents == 200
