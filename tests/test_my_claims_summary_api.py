from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import (
    Claim,
    ClaimProcedureFact,
    InsuranceCompany,
    McpCode,
    Patient,
    Role,
    User,
    UserRole,
)
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_doctor(db_session: Session, email: str) -> User:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email=email,
        password_hash=get_password_hash("secret"),
        is_active=True,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    db_session.commit()
    return user


def _seed_insurance_company(db_session: Session, name: str) -> InsuranceCompany:
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name=name)
    db_session.add(company)
    db_session.flush()
    return company


def _seed_patient(
    db_session: Session,
    doctor: User,
    first_name: str,
    last_name: str,
) -> Patient:
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=doctor.id,
        first_name=first_name,
        last_name=last_name,
        created_at=utcnow(),
    )
    db_session.add(patient)
    db_session.flush()
    return patient


def _seed_claim(
    db_session: Session,
    doctor: User,
    patient: Patient,
    company: InsuranceCompany,
    *,
    claim_number: str | None = None,
    service_date: date | None = None,
) -> Claim:
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=doctor.id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_number=claim_number,
        service_date=service_date,
        created_at=utcnow(),
    )
    db_session.add(claim)
    return claim


def _seed_mcp_code(db_session: Session, code: str) -> McpCode:
    mcp = McpCode(code=code, description="Test")
    db_session.add(mcp)
    db_session.flush()
    return mcp


def _override_db(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


def test_my_claims_summary_returns_only_current_doctor_claims(db_session: Session) -> None:
    doctor_one = _seed_doctor(db_session, "doctor1@example.com")
    doctor_two = _seed_doctor(db_session, "doctor2@example.com")

    company_one = _seed_insurance_company(db_session, "Company One")
    company_two = _seed_insurance_company(db_session, "Company Two")

    patient_one = _seed_patient(db_session, doctor_one, "John", "Smith")
    patient_two = _seed_patient(db_session, doctor_two, "Alice", "Brown")

    _seed_claim(
        db_session,
        doctor_one,
        patient_one,
        company_one,
        claim_number="CLM-1",
        service_date=date(2026, 2, 1),
    )
    _seed_claim(
        db_session,
        doctor_two,
        patient_two,
        company_two,
        claim_number="CLM-2",
        service_date=date(2026, 2, 2),
    )
    db_session.commit()

    token = create_access_token(str(doctor_one.id))
    _override_db(db_session)
    client = TestClient(app)
    try:
        response = client.get(
            "/api/claims/my-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert [item["claim_number"] for item in payload["items"]] == ["CLM-1"]
    finally:
        app.dependency_overrides.clear()


def test_my_claims_summary_aggregates_amounts_from_line_items(db_session: Session) -> None:
    doctor = _seed_doctor(db_session, "doctor@example.com")
    company = _seed_insurance_company(db_session, "Company A")
    patient = _seed_patient(db_session, doctor, "Jane", "Doe")
    claim = _seed_claim(
        db_session,
        doctor,
        patient,
        company,
        claim_number="CLM-AGG",
        service_date=date(2026, 2, 1),
    )
    code_one = _seed_mcp_code(db_session, "99213")
    code_two = _seed_mcp_code(db_session, "99214")

    base_line_id = next_id(db_session, ClaimProcedureFact)
    # Composite PK/unique constraints require distinct identifier values per line item.
    line_one = ClaimProcedureFact(
        id=base_line_id,
        claim_id=claim.id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        mcp_code=code_one.code,
        billed_amount=100.0,
        allowed_amount=60.0,
        created_at=utcnow(),
    )
    line_two = ClaimProcedureFact(
        id=base_line_id + 1,
        claim_id=claim.id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        mcp_code=code_two.code,
        billed_amount=50.0,
        allowed_amount=30.0,
        created_at=utcnow(),
    )
    db_session.add_all([line_one, line_two])
    db_session.commit()

    token = create_access_token(str(doctor.id))
    _override_db(db_session)
    client = TestClient(app)
    try:
        response = client.get(
            "/api/claims/my-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        item = payload["items"][0]
        assert item["paid_amount"] == pytest.approx(150.0)
        assert item["billed_amount"] == pytest.approx(90.0)
    finally:
        app.dependency_overrides.clear()


def test_my_claims_summary_pagination_limit_offset(db_session: Session) -> None:
    doctor = _seed_doctor(db_session, "doctor@example.com")
    company = _seed_insurance_company(db_session, "Company A")
    patient = _seed_patient(db_session, doctor, "Jane", "Doe")

    claims: list[Claim] = []
    for idx, service_date in enumerate(
        [
            date(2026, 2, 1),
            date(2026, 2, 2),
            date(2026, 2, 3),
            date(2026, 2, 4),
            date(2026, 2, 5),
        ]
    ):
        claim = _seed_claim(
            db_session,
            doctor,
            patient,
            company,
            claim_number=f"CLM-{idx}",
            service_date=service_date,
        )
        claims.append(claim)
    db_session.commit()

    sorted_claims = sorted(claims, key=lambda item: item.service_date, reverse=True)
    page_one_expected = [sorted_claims[0].claim_number, sorted_claims[1].claim_number]
    page_two_expected = [sorted_claims[2].claim_number, sorted_claims[3].claim_number]

    token = create_access_token(str(doctor.id))
    _override_db(db_session)
    client = TestClient(app)
    try:
        page_one = client.get(
            "/api/claims/my-summary",
            params={"limit": 2, "offset": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert page_one.status_code == 200
        page_one_payload = page_one.json()
        assert page_one_payload["total"] == 5
        assert [item["claim_number"] for item in page_one_payload["items"]] == page_one_expected

        page_two = client.get(
            "/api/claims/my-summary",
            params={"limit": 2, "offset": 2},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert page_two.status_code == 200
        page_two_payload = page_two.json()
        assert page_two_payload["total"] == 5
        assert [item["claim_number"] for item in page_two_payload["items"]] == page_two_expected
    finally:
        app.dependency_overrides.clear()


def test_my_claims_summary_search_by_patient_or_claim_number(db_session: Session) -> None:
    doctor = _seed_doctor(db_session, "doctor@example.com")
    company = _seed_insurance_company(db_session, "Company A")

    patient_one = _seed_patient(db_session, doctor, "John", "Smith")
    patient_two = _seed_patient(db_session, doctor, "Alice", "Brown")

    _seed_claim(
        db_session,
        doctor,
        patient_one,
        company,
        claim_number="CLM-SMITH",
        service_date=date(2026, 2, 1),
    )
    _seed_claim(
        db_session,
        doctor,
        patient_two,
        company,
        claim_number="CLM-OTHER",
        service_date=date(2026, 2, 2),
    )
    db_session.commit()

    token = create_access_token(str(doctor.id))
    _override_db(db_session)
    client = TestClient(app)
    try:
        by_name = client.get(
            "/api/claims/my-summary",
            params={"q": "smith"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert by_name.status_code == 200
        by_name_payload = by_name.json()
        assert by_name_payload["total"] == 1
        assert [item["claim_number"] for item in by_name_payload["items"]] == ["CLM-SMITH"]

        by_claim_number = client.get(
            "/api/claims/my-summary",
            params={"q": "CLM-OTHER"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert by_claim_number.status_code == 200
        by_claim_payload = by_claim_number.json()
        assert by_claim_payload["total"] == 1
        assert [item["claim_number"] for item in by_claim_payload["items"]] == ["CLM-OTHER"]
    finally:
        app.dependency_overrides.clear()


def test_my_claims_summary_requires_auth(db_session: Session) -> None:
    _override_db(db_session)
    client = TestClient(app)
    try:
        response = client.get("/api/claims/my-summary")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
