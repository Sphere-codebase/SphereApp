from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import (
    ChatSession,
    Claim,
    Clinic,
    DiagnosisCode,
    InsuranceCompany,
    McpCode,
    Patient,
    PolicyLink,
    PolicyRule,
    Role,
    User,
    UserRole,
)
from app.db.session import get_db
from app.llm.client import ChatCompletionResult, ToolCall
from app.main import app
from app.services.claims.virtual_claims import (
    bootstrap_virtual_claim_context,
    ensure_virtual_claim_draft,
    update_virtual_claim_fields,
)
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


def test_virtual_claim_materialize_confirmation_writes(db_session: Session) -> None:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="doctor-virtual@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=1,
        created_at=utcnow(),
    )
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Aetna")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=1,
        first_name="DAVID R",
        last_name="WIENTZEN",
        created_at=utcnow(),
    )
    mcp = McpCode(
        code="62323",
        description="Injection(s), of diagnostic or therapeutic substance(s)",
    )
    diagnosis = DiagnosisCode(code="M54.16", description="Radiculopathy, lumbar region")
    policy_link = PolicyLink(
        id=next_id(db_session, PolicyLink),
        insurance_company_id=company.id,
        mcp_code=mcp.code,
        policy_url="https://example.com/aetna-62323",
        created_at=utcnow(),
    )
    policy_rule = PolicyRule(
        id=next_id(db_session, PolicyRule),
        policy_link_id=policy_link.id,
        extracted_at=utcnow(),
        title="Aetna 62323 Medical Necessity",
        rules_json=(
            '{"criteria": ["radiculopathy", "functional limitation", "fluoroscopy", '
            '"physical therapy", "neuro exam", "radiologic findings", "mri", "session limit"]}'
        ),
    )
    session = ChatSession(
        id=next_id(db_session, ChatSession),
        doctor_id=user.id,
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add_all(
        [
            user,
            UserRole(user_id=user.id, role_id=doctor_role.id),
            company,
            patient,
            mcp,
            diagnosis,
            policy_link,
            policy_rule,
            session,
        ]
    )
    db_session.commit()

    bootstrap_virtual_claim_context(
        db_session,
        session,
        patient_id=patient.id,
        insurance_company_id=company.id,
        procedure_code="62323",
    )
    draft = ensure_virtual_claim_draft(db_session, session)
    update_virtual_claim_fields(
        db_session,
        draft,
        field_updates=[
            ("service_date", "2025-05-27"),
            ("diagnosis.code", "M54.16"),
            ("clinical.radiculopathy", True),
            ("clinical.functional_limitation", True),
            ("clinical.conservative_treatment", True),
            ("clinical.imaging_guidance", True),
            ("clinical.radiology_consistency", True),
            ("clinical.neuro_exam", True),
            ("clinical.mri_or_emg", True),
            ("utilization.frequency_limit_ok", True),
        ],
    )

    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Materialize the draft",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="propose_materialize_virtual_claim",
                    arguments={},
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
            json={"message": "Create the claim draft", "session_id": session.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["action_required"] is True
        assert payload["proposed_changes"]["tool"] == "propose_materialize_virtual_claim"

        confirm = client.post(
            "/api/chat/confirm-action",
            json={
                "session_id": session.id,
                "proposal_id": payload["proposed_changes"]["proposal_id"],
                "decision": "confirm",
                "tool": "propose_materialize_virtual_claim",
                "arguments": {},
                "payload": payload["proposed_changes"]["proposed_changes"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert confirm.status_code == 200
        confirmed = confirm.json()
        claim_id = confirmed["result"]["claim_id"]
        assert isinstance(claim_id, int)
        db_session.refresh(session)
        assert session.claim_id == claim_id
    finally:
        app.dependency_overrides.clear()


def test_chat_response_includes_virtual_claim_after_bootstrap_tool(db_session: Session) -> None:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="doctor-virtual-bootstrap@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=1,
        created_at=utcnow(),
    )
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Aetna")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=1,
        first_name="DAVID R",
        last_name="WIENTZEN",
        created_at=utcnow(),
    )
    mcp = McpCode(
        code="62323",
        description="Injection(s), of diagnostic or therapeutic substance(s)",
    )
    session = ChatSession(
        id=next_id(db_session, ChatSession),
        doctor_id=user.id,
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add_all(
        [user, UserRole(user_id=user.id, role_id=doctor_role.id), company, patient, mcp, session]
    )
    db_session.commit()

    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Bootstrapping the checklist",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="bootstrap_virtual_claim_context",
                    arguments={
                        "patient_id": patient.id,
                        "insurance_company_id": company.id,
                        "procedure_code": "62323",
                    },
                )
            ],
        ),
        ChatCompletionResult(assistant_text="Checklist initialized", tool_calls=[]),
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
            json={"message": "Prepare a claim checklist", "session_id": session.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["virtual_claim"] is not None
        assert (
            payload["virtual_claim"]["checklist"]["service"]["procedure_code"]["value"]
            == "62323"
        )
        assert any(action["type"] == "virtual_claim_update" for action in payload["ui_actions"])
    finally:
        app.dependency_overrides.clear()


def test_chat_message_service_date_is_applied_to_virtual_claim(db_session: Session) -> None:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="doctor-virtual-service-date@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=1,
        created_at=utcnow(),
    )
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Aetna")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=1,
        first_name="DAVID R",
        last_name="WIENTZEN",
        created_at=utcnow(),
    )
    mcp = McpCode(
        code="62323",
        description="Injection(s), of diagnostic or therapeutic substance(s)",
    )
    session = ChatSession(
        id=next_id(db_session, ChatSession),
        doctor_id=user.id,
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add_all(
        [user, UserRole(user_id=user.id, role_id=doctor_role.id), company, patient, mcp, session]
    )
    db_session.commit()

    token = create_access_token(str(user.id))
    responses = [ChatCompletionResult(assistant_text="unused", tool_calls=[])]
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
            json={
                "message": (
                    "I want to prepare a new Aetna claim for patient DAVID R WIENTZEN "
                    "for CPT 62323. Planned service date is 2025-05-27."
                ),
                "session_id": session.id,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert fake_llm.calls == 0
        assert payload["virtual_claim"] is not None
        assert payload["virtual_claim"]["patient"]["name"] == "DAVID R WIENTZEN"
        assert payload["virtual_claim"]["payer"]["name"] == "Aetna"
        assert payload["virtual_claim"]["procedure"]["code"] == "62323"
        assert payload["virtual_claim"]["checklist"]["service"]["service_date"]["value"] == (
            "2025-05-27"
        )
        assert "UPDATED" in payload["assistant_message"]
        assert "STILL MISSING" in payload["assistant_message"]
    finally:
        app.dependency_overrides.clear()


def test_chat_clinical_facts_update_existing_virtual_claim_without_duplicate_base_form(
    db_session: Session,
) -> None:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="doctor-virtual-clinical@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=1,
        created_at=utcnow(),
    )
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Aetna")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=1,
        first_name="DAVID R",
        last_name="WIENTZEN",
        created_at=utcnow(),
    )
    mcp = McpCode(
        code="62323",
        description="Injection(s), of diagnostic or therapeutic substance(s)",
    )
    diagnosis = DiagnosisCode(code="M54.16", description="Radiculopathy, lumbar region")
    policy_link = PolicyLink(
        id=next_id(db_session, PolicyLink),
        insurance_company_id=company.id,
        mcp_code=mcp.code,
        policy_url="https://example.com/aetna-62323",
        created_at=utcnow(),
    )
    policy_rule = PolicyRule(
        id=next_id(db_session, PolicyRule),
        policy_link_id=policy_link.id,
        extracted_at=utcnow(),
        title="Aetna 62323 Medical Necessity",
        rules_json=(
            '{"criteria": ["radiculopathy", "dermatomal", "functional limitation", '
            '"fluoroscopy", "physical therapy", "neuro exam", "radiologic findings", '
            '"mri", "session limit", "level limits"]}'
        ),
    )
    session = ChatSession(
        id=next_id(db_session, ChatSession),
        doctor_id=user.id,
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add_all(
        [
            user,
            UserRole(user_id=user.id, role_id=doctor_role.id),
            company,
            patient,
            mcp,
            diagnosis,
            policy_link,
            policy_rule,
            session,
        ]
    )
    db_session.commit()

    bootstrap_virtual_claim_context(
        db_session,
        session,
        patient_id=patient.id,
        insurance_company_name="Aetna",
        procedure_code="62323",
    )

    token = create_access_token(str(user.id))
    responses = [ChatCompletionResult(assistant_text="unused", tool_calls=[])]
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
            json={
                "message": (
                    "The diagnosis is M54.16 lumbar radiculopathy. The patient has dermatomal "
                    "lumbar radicular pain with significant functional limitation. Physical "
                    "therapy and non-narcotic analgesics failed. Fluoroscopy guidance will be "
                    "used. MRI within 12 months shows nerve root compression consistent with "
                    "symptoms. Neuro exam within 3 months shows altered sensation and diminished "
                    "reflexes. This is the initial therapeutic TFESI, quantity 1, one level, "
                    "and session/frequency limits are respected."
                ),
                "session_id": session.id,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert fake_llm.calls == 0
        assert payload["virtual_claim"] is not None
        assert payload["virtual_claim"]["patient"]["name"] == "DAVID R WIENTZEN"
        assert payload["virtual_claim"]["payer"]["name"] == "Aetna"
        assert payload["virtual_claim"]["procedure"]["code"] == "62323"
        assert payload["virtual_claim"]["checklist"]["diagnosis"]["diagnosis_code"]["value"] == (
            "M54.16"
        )
        assert payload["virtual_claim"]["checklist"]["diagnosis"]["diagnosis_description"][
            "value"
        ] == "Lumbar radiculopathy"
        assert (
            payload["virtual_claim"]["checklist"]["policy_medical_necessity"][
                "dermatomal_distribution"
            ]["value"]
            == (
                "The patient has dermatomal lumbar radicular pain with significant "
                "functional limitation."
            )
        )
        assert (
            payload["virtual_claim"]["checklist"]["policy_medical_necessity"][
                "initial_therapeutic_tfesi"
            ]["value"]
            == (
                "This is the initial therapeutic TFESI, quantity 1, one level, and "
                "session/frequency limits are respected."
            )
        )
        assert payload["virtual_claim"]["checklist"]["service"]["quantity"]["value"] == 1
        rendered = payload["assistant_message"].lower()
        assert "patient" not in rendered
        assert "payer" not in rendered
        assert "cpt" not in rendered
        assert all(action.get("type") != "form" for action in payload["ui_actions"])
    finally:
        app.dependency_overrides.clear()
