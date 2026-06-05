from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_stedi_claim_status_client
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import (
    Claim,
    ClaimStatusCheck,
    Clinic,
    InsuranceCompany,
    Patient,
    PatientInsurancePolicy,
    User,
)
from app.db.session import get_db
from app.main import app
from app.services.stedi.claim_status import build_claim_status_payload
from app.services.stedi.client import (
    NormalizedClaimStatus,
    StediClaimStatusError,
    StediClaimStatusSuccess,
)
from app.utils.time import utcnow


class FakeStediClient:
    def __init__(self, result: StediClaimStatusSuccess | StediClaimStatusError) -> None:
        self.result = result
        self.payloads: list[dict] = []

    def check_claim_status(self, payload: dict):
        self.payloads.append(payload)
        return self.result


def _seed_user(db: Session, clinic: Clinic, email: str, role: str = "doctor") -> User:
    user = User(
        id=next_id(db, User),
        clinic_id=clinic.id,
        email=email,
        password_hash=get_password_hash("secret"),
        full_name=email,
        role=role,
        is_active=True,
        created_at=utcnow(),
    )
    db.add(user)
    db.flush()
    return user


def _seed_claim(db: Session, *, clinic_name: str = "Clinic A") -> tuple[Clinic, User, Claim]:
    clinic = Clinic(
        id=next_id(db, Clinic),
        name=clinic_name,
        billing_provider_npi="1999999984",
        billing_provider_organization_name="Provider Name",
        created_at=utcnow(),
    )
    db.add(clinic)
    db.flush()
    user = _seed_user(db, clinic, f"{clinic_name.lower().replace(' ', '')}@example.com")
    patient = Patient(
        id=next_id(db, Patient),
        doctor_id=user.id,
        clinic_id=clinic.id,
        first_name="Jane",
        last_name="Doe",
        date_of_birth=date(1971, 1, 1),
        gender="F",
        chart_number="ACCT-123",
        created_at=utcnow(),
    )
    payer = InsuranceCompany(
        id=next_id(db, InsuranceCompany),
        name=f"{clinic_name} Payer",
        stedi_trading_partner_service_id="87726",
        created_at=utcnow(),
    )
    db.add_all([patient, payer])
    db.flush()
    policy = PatientInsurancePolicy(
        id=next_id(db, PatientInsurancePolicy),
        clinic_id=clinic.id,
        patient_id=patient.id,
        insurance_company_id=payer.id,
        priority="primary",
        member_id="UHC123456",
        created_at=utcnow(),
    )
    claim = Claim(
        id=next_id(db, Claim),
        doctor_id=user.id,
        clinic_id=clinic.id,
        patient_id=patient.id,
        insurance_company_id=payer.id,
        service_date=date(2025, 6, 30),
        claim_number="CLM-123",
        claim_status="SUBMITTED",
        billed_amount_total=Decimal("267.54"),
        created_at=utcnow(),
    )
    db.add_all([policy, claim])
    db.commit()
    return clinic, user, claim


def _client(db_session: Session, fake: FakeStediClient | None = None) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    if fake is not None:
        app.dependency_overrides[get_stedi_claim_status_client] = lambda: fake
    return TestClient(app)


def _enable_stedi(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stedi_enabled", True)
    monkeypatch.setattr(settings, "stedi_api_key", "test_stedi_secret")


def test_claim_status_payload_mapping(db_session: Session, monkeypatch) -> None:
    _enable_stedi(monkeypatch)
    _, _, claim = _seed_claim(db_session)

    result = build_claim_status_payload(db_session, claim, settings)

    assert not isinstance(result, list)
    assert result.payload["tradingPartnerServiceId"] == "87726"
    assert result.payload["encounter"] == {
        "beginningDateOfService": "20250630",
        "endDateOfService": "20250630",
        "submittedAmount": "267.54",
        "patientAccountNumber": "ACCT-123",
    }
    assert result.payload["subscriber"]["memberId"] == "UHC123456"
    assert result.payload["subscriber"]["dateOfBirth"] == "19710101"
    assert result.payload["subscriber"]["gender"] == "F"
    assert result.payload["providers"] == [
        {
            "organizationName": "Provider Name",
            "providerType": "BillingProvider",
            "npi": "1999999984",
        }
    ]


def test_claim_status_payload_missing_required_data(db_session: Session, monkeypatch) -> None:
    _enable_stedi(monkeypatch)
    _, _, claim = _seed_claim(db_session)
    claim.patient.date_of_birth = None
    claim.insurance_company.stedi_trading_partner_service_id = None
    db_session.commit()

    result = build_claim_status_payload(db_session, claim, settings)

    assert isinstance(result, list)
    fields = {item.field for item in result}
    assert "patient.date_of_birth" in fields
    assert "insurance_company.stedi_trading_partner_service_id" in fields


def test_refresh_claim_status_success(db_session: Session, monkeypatch) -> None:
    _enable_stedi(monkeypatch)
    _, user, claim = _seed_claim(db_session)
    fake = FakeStediClient(
        StediClaimStatusSuccess(
            http_status_code=200,
            status=NormalizedClaimStatus(
                status="PAID",
                status_code="65",
                status_category="F1",
                message="Claim/line has been paid.",
                amount_paid=Decimal("108.77"),
                payer_claim_number="PAYER-123",
                trace_id="trace_123",
                claim_count=1,
            ),
            response_summary={
                "http_status_code": 200,
                "claim_count": 1,
                "status_codes": ["65"],
                "status_categories": ["F1"],
                "trace_id": "trace_123",
            },
        )
    )
    client = _client(db_session, fake)
    token = create_access_token(str(user.id))
    try:
        response = client.post(
            f"/api/claims/{claim.id}/refresh-status",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "PAID"
    assert payload["amount_paid"] == 108.77
    assert payload["payer_claim_number"] == "PAYER-123"
    assert payload["warnings"] == [
        "Claim has no submitted timestamp; status was refreshed without using submitted_at."
    ]
    db_session.refresh(claim)
    assert claim.stedi_status == "PAID"
    check = db_session.execute(select(ClaimStatusCheck)).scalar_one()
    assert check.outcome == "success"
    assert check.request_summary_json["provider_identifier"] == "npi"
    assert "Authorization" not in str(check.request_summary_json)


@pytest.mark.parametrize(
    ("mutate", "field", "message"),
    [
        (
            lambda claim: setattr(
                claim.insurance_company, "stedi_trading_partner_service_id", None
            ),
            "insurance_company.stedi_trading_partner_service_id",
            "Set the payer Stedi trading partner service ID.",
        ),
        (
            lambda claim: setattr(claim.patient.insurance_policies[0], "member_id", None),
            "patient_insurance_policy.member_id",
            "Set the patient's member ID for this payer.",
        ),
        (
            lambda claim: (
                setattr(claim.patient.clinic, "billing_provider_npi", None),
                setattr(
                    claim.patient.clinic,
                    "billing_provider_organization_name",
                    None,
                ),
            ),
            "clinic.billing_provider",
            (
                "Set clinic billing provider organization name and NPI or TIN, "
                "or configure STEDI_PROVIDER_* fallbacks."
            ),
        ),
    ],
)
def test_refresh_claim_status_missing_required_data_is_actionable(
    db_session: Session,
    monkeypatch,
    mutate,
    field: str,
    message: str,
) -> None:
    _enable_stedi(monkeypatch)
    monkeypatch.setattr(settings, "stedi_provider_npi", None)
    monkeypatch.setattr(settings, "stedi_provider_tax_id", None)
    monkeypatch.setattr(settings, "stedi_provider_organization_name", None)
    _, user, claim = _seed_claim(db_session)
    mutate(claim)
    db_session.commit()
    client = _client(db_session)
    token = create_access_token(str(user.id))
    try:
        response = client.post(
            f"/api/claims/{claim.id}/refresh-status",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "STEDI_MISSING_REQUIRED_DATA"
    missing = error["details"]["missing"]
    assert {"field": field, "message": message} in missing
    check = db_session.execute(select(ClaimStatusCheck)).scalar_one()
    assert check.outcome == "validation_error"
    assert check.error_code == "STEDI_MISSING_REQUIRED_DATA"


def test_refresh_claim_status_no_match(db_session: Session, monkeypatch) -> None:
    _enable_stedi(monkeypatch)
    _, user, claim = _seed_claim(db_session)
    fake = FakeStediClient(
        StediClaimStatusSuccess(
            http_status_code=200,
            status=NormalizedClaimStatus(
                status="NO_MATCH",
                status_code=None,
                status_category=None,
                message="No matching payer claim status was returned.",
                amount_paid=None,
                payer_claim_number=None,
                trace_id="trace_no_match",
                claim_count=0,
            ),
            response_summary={
                "http_status_code": 200,
                "claim_count": 0,
                "status_codes": [],
                "status_categories": [],
                "trace_id": "trace_no_match",
            },
        )
    )
    client = _client(db_session, fake)
    token = create_access_token(str(user.id))
    try:
        response = client.post(
            f"/api/claims/{claim.id}/refresh-status",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "NO_MATCH"
    check = db_session.execute(select(ClaimStatusCheck)).scalar_one()
    assert check.outcome == "no_match"


def test_refresh_claim_status_stedi_error(db_session: Session, monkeypatch) -> None:
    _enable_stedi(monkeypatch)
    _, user, claim = _seed_claim(db_session)
    fake = FakeStediClient(
        StediClaimStatusError(
            http_status_code=500,
            error_code="STEDI_HTTP_ERROR",
            message="Stedi returned an error while checking claim status.",
            trace_id="trace_error",
            response_summary={"http_status_code": 500, "trace_id": "trace_error"},
        )
    )
    client = _client(db_session, fake)
    token = create_access_token(str(user.id))
    try:
        response = client.post(
            f"/api/claims/{claim.id}/refresh-status",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "STEDI_HTTP_ERROR"
    check = db_session.execute(select(ClaimStatusCheck)).scalar_one()
    assert check.outcome == "stedi_error"
    db_session.refresh(claim)
    assert claim.stedi_status is None


def test_refresh_claim_status_clinic_isolation(db_session: Session, monkeypatch) -> None:
    _enable_stedi(monkeypatch)
    clinic_a = Clinic(id=next_id(db_session, Clinic), name="Clinic A", created_at=utcnow())
    db_session.add(clinic_a)
    db_session.flush()
    user_a = _seed_user(db_session, clinic_a, "doctor-a@example.com")
    clinic_b, _, claim_b = _seed_claim(db_session, clinic_name="Clinic B")
    db_session.commit()
    fake = FakeStediClient(
        StediClaimStatusError(
            http_status_code=500,
            error_code="SHOULD_NOT_CALL",
            message="Should not call",
        )
    )
    client = _client(db_session, fake)
    token = create_access_token(str(user_a.id))
    try:
        response = client.post(
            f"/api/claims/{claim_b.id}/refresh-status",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert fake.payloads == []
    assert clinic_b.id == claim_b.clinic_id


def test_refresh_claim_status_does_not_expose_api_key(
    db_session: Session, monkeypatch, caplog
) -> None:
    monkeypatch.setattr(settings, "stedi_enabled", True)
    monkeypatch.setattr(settings, "stedi_api_key", "super-secret-stedi-key")
    _, user, claim = _seed_claim(db_session)
    fake = FakeStediClient(
        StediClaimStatusError(
            http_status_code=500,
            error_code="STEDI_HTTP_ERROR",
            message="Stedi returned an error while checking claim status.",
            response_summary={"http_status_code": 500},
        )
    )
    client = _client(db_session, fake)
    token = create_access_token(str(user.id))
    try:
        response = client.post(
            f"/api/claims/{claim.id}/refresh-status",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert "super-secret-stedi-key" not in response.text
    assert "super-secret-stedi-key" not in caplog.text


def test_admin_can_maintain_stedi_payer_id(db_session: Session) -> None:
    clinic = Clinic(id=next_id(db_session, Clinic), name="Admin Clinic", created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    admin = _seed_user(
        db_session,
        clinic,
        "platform-admin@example.com",
        role="platform_staff_admin",
    )
    company = InsuranceCompany(
        id=next_id(db_session, InsuranceCompany),
        name="Payer Admin",
        created_at=utcnow(),
    )
    db_session.add(company)
    db_session.commit()
    client = _client(db_session)
    token = create_access_token(str(admin.id))
    try:
        response = client.patch(
            f"/api/admin/insurance-companies/{company.id}",
            json={
                "name": "Payer Admin",
                "stedi_trading_partner_service_id": "005010",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["stedi_trading_partner_service_id"] == "005010"
    db_session.refresh(company)
    assert company.stedi_trading_partner_service_id == "005010"


def test_admin_can_maintain_billing_provider_profile(db_session: Session) -> None:
    clinic = Clinic(id=next_id(db_session, Clinic), name="Billing Clinic", created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    admin = _seed_user(
        db_session,
        clinic,
        "billing-admin@example.com",
        role="platform_staff_admin",
    )
    db_session.commit()
    client = _client(db_session)
    token = create_access_token(str(admin.id))
    try:
        response = client.patch(
            f"/api/platform/clinics/{clinic.id}",
            json={
                "billing_provider_npi": "1999999984",
                "billing_provider_tax_id": "123456789",
                "billing_provider_organization_name": "Billing Provider LLC",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["billing_provider_npi"] == "1999999984"
    assert payload["billing_provider_tax_id"] == "123456789"
    assert payload["billing_provider_organization_name"] == "Billing Provider LLC"
    db_session.refresh(clinic)
    assert clinic.billing_provider_npi == "1999999984"
    assert clinic.billing_provider_tax_id == "123456789"
    assert clinic.billing_provider_organization_name == "Billing Provider LLC"


def test_claim_stedi_data_update_preserves_payer_id_leading_zeros(
    db_session: Session,
) -> None:
    _, user, claim = _seed_claim(db_session)
    client = _client(db_session)
    token = create_access_token(str(user.id))
    try:
        response = client.patch(
            f"/api/claims/{claim.id}/stedi-data",
            json={
                "insurance_company": {
                    "stedi_trading_partner_service_id": "005010",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["insurance_company"]["stedi_trading_partner_service_id"] == "005010"
    db_session.refresh(claim.insurance_company)
    assert claim.insurance_company.stedi_trading_partner_service_id == "005010"


def test_claim_stedi_data_update_patient_insurance_member_id(
    db_session: Session,
) -> None:
    _, user, claim = _seed_claim(db_session)
    client = _client(db_session)
    token = create_access_token(str(user.id))
    try:
        response = client.patch(
            f"/api/claims/{claim.id}/stedi-data",
            json={
                "patient_insurance_policy": {
                    "member_id": "NEW-MEMBER-123",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["patient_insurance_policy"]["member_id"] == "NEW-MEMBER-123"
    policy_record = db_session.execute(
        select(PatientInsurancePolicy).where(
            PatientInsurancePolicy.patient_id == claim.patient_id,
            PatientInsurancePolicy.insurance_company_id == claim.insurance_company_id,
        )
    ).scalar_one()
    assert policy_record.member_id == "NEW-MEMBER-123"


def test_claim_stedi_data_update_patient_insurance_group_number(
    db_session: Session,
) -> None:
    _, user, claim = _seed_claim(db_session)
    client = _client(db_session)
    token = create_access_token(str(user.id))
    try:
        response = client.patch(
            f"/api/claims/{claim.id}/stedi-data",
            json={
                "patient_insurance_policy": {
                    "member_id": "UHC123456",
                    "group_number": "GRP-009",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["patient_insurance_policy"]["group_number"] == "GRP-009"
    policy_record = db_session.execute(
        select(PatientInsurancePolicy).where(
            PatientInsurancePolicy.patient_id == claim.patient_id,
            PatientInsurancePolicy.insurance_company_id == claim.insurance_company_id,
        )
    ).scalar_one()
    assert policy_record.group_number == "GRP-009"


def test_claim_stedi_data_update_clinic_billing_provider(
    db_session: Session,
) -> None:
    clinic, user, claim = _seed_claim(db_session)
    client = _client(db_session)
    token = create_access_token(str(user.id))
    try:
        response = client.patch(
            f"/api/claims/{claim.id}/stedi-data",
            json={
                "clinic": {
                    "billing_provider_organization_name": "Billing Provider LLC",
                    "billing_provider_npi": "1999999984",
                    "billing_provider_tax_id": "123456789",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["clinic"]["billing_provider_organization_name"] == (
        "Billing Provider LLC"
    )
    assert payload["clinic"]["billing_provider_npi"] == "1999999984"
    assert payload["clinic"]["billing_provider_tax_id"] == "123456789"
    db_session.refresh(clinic)
    assert clinic.billing_provider_organization_name == "Billing Provider LLC"
    assert clinic.billing_provider_npi == "1999999984"
    assert clinic.billing_provider_tax_id == "123456789"


def test_claim_stedi_data_update_requires_billing_provider_identifier(
    db_session: Session,
) -> None:
    _, user, claim = _seed_claim(db_session)
    client = _client(db_session)
    token = create_access_token(str(user.id))
    try:
        response = client.patch(
            f"/api/claims/{claim.id}/stedi-data",
            json={
                "clinic": {
                    "billing_provider_organization_name": "Billing Provider LLC",
                    "billing_provider_npi": "",
                    "billing_provider_tax_id": "",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_cross_clinic_user_cannot_update_claim_stedi_data(
    db_session: Session,
) -> None:
    clinic_a = Clinic(id=next_id(db_session, Clinic), name="Clinic A", created_at=utcnow())
    db_session.add(clinic_a)
    db_session.flush()
    user_a = _seed_user(db_session, clinic_a, "doctor-a@example.com")
    _, _, claim_b = _seed_claim(db_session, clinic_name="Clinic B")
    db_session.commit()
    client = _client(db_session)
    token = create_access_token(str(user_a.id))
    try:
        response = client.patch(
            f"/api/claims/{claim_b.id}/stedi-data",
            json={
                "insurance_company": {
                    "stedi_trading_partner_service_id": "005010",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_claim_stedi_data_responses_do_not_expose_api_key(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "stedi_api_key", "super-secret-stedi-key")
    _, user, claim = _seed_claim(db_session)
    client = _client(db_session)
    token = create_access_token(str(user.id))
    try:
        response = client.get(
            f"/api/claims/{claim.id}/stedi-data",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "super-secret-stedi-key" not in response.text
