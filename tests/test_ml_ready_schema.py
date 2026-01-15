import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import (
    Claim,
    ClaimLineCoverage,
    ClaimProcedureDiagnosis,
    ClaimProcedureFact,
    DiagnosisCode,
    InsuranceCompany,
    McpCode,
    Patient,
    User,
)
from app.utils.time import utcnow


def _seed_claim_context(
    db_session: Session,
) -> tuple[Claim, McpCode, DiagnosisCode]:
    user = User(
        id=next_id(db_session, User),
        email="doctor@example.com",
        password_hash="hashed",
        is_active=True,
        created_at=utcnow(),
    )
    company = InsuranceCompany(
        id=next_id(db_session, InsuranceCompany),
        name="Acme Health",
        created_at=utcnow(),
    )
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        first_name="Jane",
        last_name="Doe",
        created_at=utcnow(),
    )
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=user.id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_status="DRAFT",
        created_at=utcnow(),
    )
    code = McpCode(code="99213", description="Office Visit")
    diagnosis = DiagnosisCode(code="A00", description="Cholera")
    db_session.add_all([user, company, patient, claim, code, diagnosis])
    db_session.commit()
    return claim, code, diagnosis


def test_ml_ready_schema_tables_and_columns(db_session: Session) -> None:
    inspector = inspect(db_session.get_bind())
    tables = set(inspector.get_table_names())
    for table in {
        "claim_procedure_facts",
        "claim_procedure_diagnosis",
        "claim_line_coverage",
        "policy_rules",
        "ml_training_examples",
        "ml_predictions",
        "mcp_payment_predictions",
    }:
        assert table in tables

    claim_procedure_columns = {
        column["name"] for column in inspector.get_columns("claim_procedure_facts")
    }
    for column in {
        "claim_id",
        "patient_id",
        "insurance_company_id",
        "mcp_code",
        "service_date",
        "units",
        "billed_amount",
        "allowed_amount",
        "paid_amount",
    }:
        assert column in claim_procedure_columns

    coverage_indexes = {index["name"] for index in inspector.get_indexes("claim_line_coverage")}
    assert "uq_claim_line_coverage_claim_id_mcp_code" in coverage_indexes

    prediction_indexes = {
        index["name"] for index in inspector.get_indexes("mcp_payment_predictions")
    }
    assert (
        "uq_mcp_payment_predictions_company_code_date"
        in prediction_indexes
    )


def test_claim_procedure_diagnosis_unique_constraint(db_session: Session) -> None:
    claim, code, diagnosis = _seed_claim_context(db_session)
    fact = ClaimProcedureFact(
        id=next_id(db_session, ClaimProcedureFact),
        claim_id=claim.id,
        patient_id=claim.patient_id,
        insurance_company_id=claim.insurance_company_id,
        mcp_code=code.code,
        created_at=utcnow(),
    )
    db_session.add(fact)
    db_session.commit()

    link = ClaimProcedureDiagnosis(
        claim_procedure_fact_id=fact.id,
        diagnosis_code=diagnosis.code,
    )
    db_session.add(link)
    db_session.commit()
    db_session.expunge(link)

    duplicate = ClaimProcedureDiagnosis(
        claim_procedure_fact_id=fact.id,
        diagnosis_code=diagnosis.code,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_claim_line_coverage_unique_constraint(db_session: Session) -> None:
    claim, code, _diagnosis = _seed_claim_context(db_session)
    coverage = ClaimLineCoverage(
        id=next_id(db_session, ClaimLineCoverage),
        claim_id=claim.id,
        mcp_code=code.code,
        status="COVERED",
        created_at=utcnow(),
    )
    db_session.add(coverage)
    db_session.commit()

    duplicate = ClaimLineCoverage(
        id=next_id(db_session, ClaimLineCoverage),
        claim_id=claim.id,
        mcp_code=code.code,
        status="COVERED",
        created_at=utcnow(),
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
