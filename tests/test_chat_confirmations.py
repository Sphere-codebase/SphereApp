from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Claim, Clinic, InsuranceCompany, Patient, Role, User, UserRole
from app.db.session import get_db
from app.llm.client import ChatCompletionResult, ToolCall
from app.main import app
from app.utils.time import utcnow


class FakeLLMClient:
    def __init__(self, responses: list[ChatCompletionResult]) -> None:
        self.responses = responses
        self.calls = 0

    def chat_complete(self, messages, tools, temperature=None):  # noqa: D401
        response = self.responses[self.calls]
        self.calls += 1
        return response


def _seed_clinic(db_session: Session, name: str) -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name=name, created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_claim(db_session: Session, email: str, clinic_id: int = 1) -> tuple[User, Claim]:
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
        clinic_id=clinic_id,
        created_at=utcnow(),
    )
    company_name = f"Company {email.replace('@', '-')}"
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name=company_name)
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=user.clinic_id,
        first_name="Jane",
        last_name="Doe",
        created_at=utcnow(),
    )
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=user.id,
        clinic_id=user.clinic_id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_status="DRAFT",
        created_at=utcnow(),
    )
    db_session.add_all(
        [user, UserRole(user_id=user.id, role_id=doctor_role.id), company, patient, claim]
    )
    db_session.commit()
    return user, claim


def test_update_requires_confirmation(db_session: Session) -> None:
    user, claim = _seed_claim(db_session, "doctor@example.com")
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Propose update",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="update_claim_fields",
                    arguments={"claim_id": claim.id, "patch": {"claim_status": "SUBMITTED"}},
                )
            ],
        )
    ]
    fake_llm = FakeLLMClient(responses)

    def override_get_db():
        yield db_session

    def override_llm_client():
        return fake_llm

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        response = client.post(
            "/chat",
            json={"message": "Close claim"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["action_required"] is True
        assert payload["proposed_changes"]["patch"]["claim_status"] == "SUBMITTED"

        db_session.refresh(claim)
        assert claim.claim_status == "DRAFT"
    finally:
        app.dependency_overrides.clear()


def test_update_with_confirmation_writes(db_session: Session) -> None:
    user, claim = _seed_claim(db_session, "doctor@example.com")
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Update now",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="update_claim_fields",
                    arguments={
                        "claim_id": claim.id,
                        "patch": {"claim_status": "SUBMITTED"},
                        "confirm": True,
                    },
                )
            ],
        ),
        ChatCompletionResult(assistant_text="Done", tool_calls=[]),
    ]
    fake_llm = FakeLLMClient(responses)

    def override_get_db():
        yield db_session

    def override_llm_client():
        return fake_llm

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        response = client.post(
            "/chat",
            json={"message": "Close claim"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        db_session.refresh(claim)
        assert claim.claim_status == "SUBMITTED"
    finally:
        app.dependency_overrides.clear()


def test_other_user_update_returns_404(db_session: Session) -> None:
    clinic_a = _seed_clinic(db_session, "Clinic A")
    clinic_b = _seed_clinic(db_session, "Clinic B")
    user_a, _claim_a = _seed_claim(db_session, "doctor-a@example.com", clinic_id=clinic_a.id)
    user_b, claim_b = _seed_claim(db_session, "doctor-b@example.com", clinic_id=clinic_b.id)

    token = create_access_token(str(user_a.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Update other user",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="update_claim_fields",
                    arguments={
                        "claim_id": claim_b.id,
                        "patch": {"claim_status": "DENIED"},
                        "confirm": True,
                    },
                )
            ],
        )
    ]
    fake_llm = FakeLLMClient(responses)

    def override_get_db():
        yield db_session

    def override_llm_client():
        return fake_llm

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        response = client.post(
            "/chat",
            json={"message": "Close other claim"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
