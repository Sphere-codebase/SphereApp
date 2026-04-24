import json
import threading
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import create_access_token, get_password_hash
from app.core.tenancy import reset_current_is_platform_admin, set_current_is_platform_admin
from app.db.id_utils import next_id
from app.db.models import (
    ChatSession,
    Claim,
    Clinic,
    DiagnosisCode,
    InsuranceCompany,
    McpCode,
    Patient,
    PatientInsurancePolicy,
    PolicyLink,
    PolicyRule,
    Role,
    User,
    UserRole,
    VirtualClaimDraft,
    VirtualClaimField,
    VirtualClaimQuestion,
)
from app.db.session import get_db
from app.main import app
from app.services.claims.virtual_claims import (
    bootstrap_virtual_claim_context,
    ensure_virtual_claim_draft,
    recompute_virtual_claim,
    update_virtual_claim_fields,
)
from app.utils.time import utcnow


def _seed_clinic(db_session: Session) -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name="Clinic One", created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_doctor(db_session: Session, clinic_id: int) -> User:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="virtual-claim@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=clinic_id,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    db_session.flush()
    return user


def _seed_virtual_claim_context(
    db_session: Session,
) -> tuple[User, ChatSession, Patient, InsuranceCompany]:
    clinic = _seed_clinic(db_session)
    user = _seed_doctor(db_session, clinic.id)
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Aetna")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=clinic.id,
        first_name="DAVID R",
        last_name="WIENTZEN",
        date_of_birth=date(1966, 8, 31),
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
        rules_json=json.dumps(
            {
                    "criteria": [
                        "Radiculopathy with dermatomal pain/symptoms and functional limitation",
                        "Fluoroscopy or CT guidance",
                        (
                            "Failed conservative treatment such as physical therapy "
                            "and non-narcotic analgesics"
                        ),
                        "MRI/CT or EMG/NCV evidence of nerve root compression",
                        "Recent neuro exam findings",
                        "Session frequency and annual limits apply",
                ]
            }
        ),
    )
    session = ChatSession(
        id=next_id(db_session, ChatSession),
        doctor_id=user.id,
        clinic_id=clinic.id,
        created_at=utcnow(),
    )
    patient_policy = PatientInsurancePolicy(
        id=next_id(db_session, PatientInsurancePolicy),
        clinic_id=clinic.id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        priority="primary",
        member_id="AETNA-MEMBER-1",
        created_at=utcnow(),
    )
    db_session.add_all(
        [company, patient, patient_policy, mcp, diagnosis, policy_link, policy_rule, session]
    )
    db_session.commit()
    return user, session, patient, company


def test_virtual_claim_checklist_flow(db_session: Session) -> None:
    user, session, patient, company = _seed_virtual_claim_context(db_session)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/chat/sessions/{session.id}/virtual-claim",
            json={
                "patient_id": patient.id,
                "insurance_company_id": company.id,
                "procedure_code": "62323",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["patient"]["name"] == "DAVID R WIENTZEN"
        assert payload["payer"]["name"] == "Aetna"
        assert payload["procedure"]["code"] == "62323"
        assert payload["readiness"] is False
        assert payload["missing_fields"]
        question_rows = (
            db_session.execute(
                select(VirtualClaimQuestion)
                .where(VirtualClaimQuestion.draft_id == payload["draft_id"])
                .order_by(VirtualClaimQuestion.id.asc())
            )
            .scalars()
            .all()
        )
        assert len(question_rows) >= 4
        assert len({row.id for row in question_rows}) == len(question_rows)
        assert {row.question_key for row in question_rows}.issuperset(
            {"patient_id", "insurance_company_id", "procedure_code", "service_date"}
        )
        assert payload["checklist"]["patient"]["first_name"]["value"] == "DAVID R"
        assert payload["checklist"]["payer_insurance"]["member_id"]["value"] == "AETNA-MEMBER-1"
        assert payload["checklist"]["service"]["procedure_description"]["value"] == (
            "Injection(s), of diagnostic or therapeutic substance(s)"
        )
        assert payload["checklist"]["policy_medical_necessity"]["stored_rules_available"][
            "status"
        ] == "derived"

        patch_response = client.patch(
            f"/api/chat/sessions/{session.id}/virtual-claim",
            json={
                "fields": [
                    {"key": "service_date", "value": "2025-05-27"},
                    {"key": "diagnosis.code", "value": "M54.16"},
                    {"key": "clinical.radiculopathy", "value": True},
                    {"key": "clinical.functional_limitation", "value": True},
                    {"key": "clinical.conservative_treatment", "value": True},
                    {"key": "clinical.imaging_guidance", "value": True},
                    {"key": "clinical.radiology_consistency", "value": True},
                    {"key": "clinical.neuro_exam", "value": True},
                    {"key": "clinical.mri_or_emg", "value": True},
                    {"key": "utilization.frequency_limit_ok", "value": True},
                ]
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert patch_response.status_code == 200
        updated = patch_response.json()
        assert updated["readiness"] is True
        assert updated["missing_fields"] == []
        assert updated["checklist"]["readiness"]["ready_to_draft"] is True

        proposal_response = client.post(
            f"/api/chat/sessions/{session.id}/virtual-claim/materialize",
            json={"confirm": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert proposal_response.status_code == 200
        proposal_payload = proposal_response.json()
        assert proposal_payload["action_required"] is True
        assert proposal_payload["proposal"]["summary"]["procedure_code"] == "62323"

        confirm_response = client.post(
            f"/api/chat/sessions/{session.id}/virtual-claim/materialize",
            json={"confirm": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert confirm_response.status_code == 200
        confirmed = confirm_response.json()
        assert confirmed["claim_id"] is not None

        db_session.refresh(session)
        assert session.claim_id == confirmed["claim_id"]
        claim = (
            db_session.execute(select(Claim).where(Claim.id == confirmed["claim_id"]))
            .scalar_one()
        )
        assert claim.patient_id == patient.id
        assert claim.insurance_company_id == company.id
    finally:
        app.dependency_overrides.clear()


def test_virtual_claim_endpoint_is_idempotent_for_repeated_calls(db_session: Session) -> None:
    user, session, patient, company = _seed_virtual_claim_context(db_session)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        payload = {
            "patient_id": patient.id,
            "insurance_company_id": company.id,
            "procedure_code": "62323",
        }
        for _ in range(3):
            response = client.post(
                f"/api/chat/sessions/{session.id}/virtual-claim",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200

        drafts = (
            db_session.execute(
                select(VirtualClaimDraft)
                .where(VirtualClaimDraft.chat_session_id == session.id)
                .order_by(VirtualClaimDraft.id.asc())
            )
            .scalars()
            .all()
        )
        field_rows = (
            db_session.execute(
                select(VirtualClaimField)
                .join(VirtualClaimDraft, VirtualClaimDraft.id == VirtualClaimField.draft_id)
                .where(VirtualClaimDraft.chat_session_id == session.id)
            )
            .scalars()
            .all()
        )
        question_rows = (
            db_session.execute(
                select(VirtualClaimQuestion)
                .join(VirtualClaimDraft, VirtualClaimDraft.id == VirtualClaimQuestion.draft_id)
                .where(VirtualClaimDraft.chat_session_id == session.id)
            )
            .scalars()
            .all()
        )

        assert len(drafts) == 1
        assert len({(row.draft_id, row.field_key) for row in field_rows}) == len(field_rows)
        assert len({(row.draft_id, row.question_key) for row in question_rows}) == len(
            question_rows
        )
    finally:
        app.dependency_overrides.clear()


def test_patient_selection_fills_patient_checklist(db_session: Session) -> None:
    user, session, patient, _company = _seed_virtual_claim_context(db_session)
    response = bootstrap_virtual_claim_context(db_session, session, patient_id=patient.id)

    assert response.checklist.patient.patient_id.status == "present"
    assert response.checklist.patient.patient_id.value == patient.id
    assert response.checklist.patient.first_name.value == "DAVID R"
    assert response.checklist.patient.last_name.value == "WIENTZEN"
    assert response.checklist.patient.date_of_birth.value == "1966-08-31"
    assert response.readiness is False


def test_ensure_virtual_claim_draft_is_idempotent(db_session: Session) -> None:
    _user, session, _patient, _company = _seed_virtual_claim_context(db_session)

    first = ensure_virtual_claim_draft(db_session, session)
    second = ensure_virtual_claim_draft(db_session, session)

    drafts = (
        db_session.execute(
            select(VirtualClaimDraft)
            .where(VirtualClaimDraft.chat_session_id == session.id)
            .order_by(VirtualClaimDraft.id.asc())
        )
        .scalars()
        .all()
    )

    assert first.id == second.id
    assert len(drafts) == 1


def test_payer_and_62323_fill_procedure_and_policy_checklist(db_session: Session) -> None:
    _user, session, patient, company = _seed_virtual_claim_context(db_session)
    response = bootstrap_virtual_claim_context(
        db_session,
        session,
        patient_id=patient.id,
        insurance_company_id=company.id,
        procedure_code="62323",
    )

    assert response.checklist.payer_insurance.payer_name.value == "Aetna"
    assert response.checklist.payer_insurance.member_id.value == "AETNA-MEMBER-1"
    assert response.checklist.service.procedure_code.value == "62323"
    assert response.checklist.service.procedure_description.value == (
        "Injection(s), of diagnostic or therapeutic substance(s)"
    )
    assert response.checklist.policy_medical_necessity.policy_link_id.status == "derived"
    assert response.checklist.policy_medical_necessity.policy_url.value == (
        "https://example.com/aetna-62323"
    )
    assert response.checklist.policy_medical_necessity.stored_rules_available.value is True


def test_bootstrap_virtual_claim_context_normalizes_common_live_variants(
    db_session: Session,
) -> None:
    _user, session, patient, _company = _seed_virtual_claim_context(db_session)
    response = bootstrap_virtual_claim_context(
        db_session,
        session,
        patient_id=str(patient.id),
        insurance_company_id="Aetna",
        procedure_code="CPT62323",
    )

    assert response.patient is not None
    assert response.patient.id == patient.id
    assert response.payer is not None
    assert response.payer.name == "Aetna"
    assert response.procedure is not None
    assert response.procedure.code == "62323"
    assert response.checklist.service.procedure_code.value == "62323"


def test_missing_clinical_facts_keeps_virtual_claim_not_ready(db_session: Session) -> None:
    _user, session, patient, company = _seed_virtual_claim_context(db_session)
    response = bootstrap_virtual_claim_context(
        db_session,
        session,
        patient_id=patient.id,
        insurance_company_id=company.id,
        procedure_code="62323",
    )

    assert response.checklist.readiness.ready_to_draft is False
    assert "service.service_date" in response.checklist.readiness.missing_fields
    assert (
        "policy_medical_necessity.radiculopathy_evidence"
        in response.checklist.readiness.missing_fields
    )


def test_all_required_facts_mark_virtual_claim_ready(db_session: Session) -> None:
    _user, session, patient, company = _seed_virtual_claim_context(db_session)
    bootstrap_virtual_claim_context(
        db_session,
        session,
        patient_id=patient.id,
        insurance_company_id=company.id,
        procedure_code="62323",
    )
    draft = ensure_virtual_claim_draft(db_session, session)
    response = update_virtual_claim_fields(
        db_session,
        draft,
        field_updates=[
            ("service_date", "2025-05-27"),
            ("diagnosis.code", "M54.16"),
            ("clinical.radiculopathy", True),
            ("clinical.functional_limitation", True),
            ("clinical.conservative_treatment", True),
            ("clinical.imaging_guidance", True),
            ("clinical.neuro_exam", True),
            ("clinical.mri_or_emg", True),
            ("utilization.frequency_limit_ok", True),
        ],
    )

    assert response.checklist.readiness.ready_to_draft is True
    assert response.checklist.readiness.missing_fields == []
    assert (
        response.checklist.diagnosis.diagnosis_description.value
        == "Radiculopathy, lumbar region"
    )


def test_recompute_virtual_claim_is_idempotent_for_fields_and_questions(
    db_session: Session,
) -> None:
    _user, session, patient, company = _seed_virtual_claim_context(db_session)
    bootstrap_virtual_claim_context(
        db_session,
        session,
        patient_id=patient.id,
        insurance_company_id=company.id,
        procedure_code="62323",
    )
    draft = ensure_virtual_claim_draft(db_session, session)

    first = recompute_virtual_claim(db_session, draft)
    second = recompute_virtual_claim(db_session, draft)

    rendering_provider_fields = (
        db_session.execute(
            select(VirtualClaimField)
            .where(
                VirtualClaimField.draft_id == draft.id,
                VirtualClaimField.field_key == "service.rendering_provider",
            )
            .order_by(VirtualClaimField.id.asc())
        )
        .scalars()
        .all()
    )
    question_rows = (
        db_session.execute(
            select(VirtualClaimQuestion)
            .where(VirtualClaimQuestion.draft_id == draft.id)
            .order_by(VirtualClaimQuestion.id.asc())
        )
        .scalars()
        .all()
    )

    assert first.draft_id == second.draft_id
    assert len(rendering_provider_fields) <= 1
    assert len({row.question_key for row in question_rows}) == len(question_rows)


def test_updating_multiple_virtual_claim_fields_assigns_unique_ids(db_session: Session) -> None:
    _user, session, patient, company = _seed_virtual_claim_context(db_session)
    bootstrap_virtual_claim_context(
        db_session,
        session,
        patient_id=patient.id,
        insurance_company_id=company.id,
        procedure_code="62323",
    )
    draft = ensure_virtual_claim_draft(db_session, session)

    response = update_virtual_claim_fields(
        db_session,
        draft,
        field_updates=[
            ("service_date", "2025-05-27"),
            ("diagnosis.code", "M54.16"),
            ("clinical.radiculopathy", True),
            ("clinical.functional_limitation", True),
        ],
    )

    field_rows = (
        db_session.execute(
            select(VirtualClaimField)
            .where(
                VirtualClaimField.draft_id == draft.id,
                VirtualClaimField.field_key.in_(
                    [
                        "service_date",
                        "diagnosis.code",
                        "clinical.radiculopathy",
                        "clinical.functional_limitation",
                    ]
                ),
            )
            .order_by(VirtualClaimField.id.asc())
        )
        .scalars()
        .all()
    )

    assert response.checklist.service.service_date.value == "2025-05-27"
    assert len(field_rows) == 4
    assert len({row.id for row in field_rows}) == len(field_rows)


def test_concurrent_virtual_claim_bootstrap_does_not_create_duplicate_draft(
    db_session: Session,
) -> None:
    engine = db_session.get_bind()
    assert engine is not None
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    _user, session, patient, company = _seed_virtual_claim_context(db_session)
    barrier = threading.Barrier(2)
    errors: list[Exception] = []
    error_lock = threading.Lock()

    def worker() -> None:
        token = set_current_is_platform_admin(True)
        thread_session = SessionLocal()
        try:
            current_session = thread_session.get(ChatSession, session.id)
            assert current_session is not None
            barrier.wait(timeout=5)
            response = bootstrap_virtual_claim_context(
                thread_session,
                current_session,
                patient_id=patient.id,
                insurance_company_id=company.id,
                procedure_code="62323",
            )
            assert response.draft_id is not None
        except Exception as exc:  # pragma: no cover - assertion covers unexpected failures
            thread_session.rollback()
            with error_lock:
                errors.append(exc)
        finally:
            thread_session.close()
            reset_current_is_platform_admin(token)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    drafts = (
        db_session.execute(
            select(VirtualClaimDraft)
            .where(VirtualClaimDraft.chat_session_id == session.id)
            .order_by(VirtualClaimDraft.id.asc())
        )
        .scalars()
        .all()
    )

    assert not errors
    assert len(drafts) == 1


def test_missing_policy_data_stays_unknown_without_hallucination(db_session: Session) -> None:
    clinic = _seed_clinic(db_session)
    user = _seed_doctor(db_session, clinic.id)
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="No Rules Plan")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=clinic.id,
        first_name="Avril",
        last_name="Jeffrey",
        date_of_birth=date(1949, 7, 22),
        created_at=utcnow(),
    )
    mcp = McpCode(
        code="62323",
        description="Injection(s), of diagnostic or therapeutic substance(s)",
    )
    session = ChatSession(
        id=next_id(db_session, ChatSession),
        doctor_id=user.id,
        clinic_id=clinic.id,
        created_at=utcnow(),
    )
    db_session.add_all([company, patient, mcp, session])
    db_session.commit()

    bootstrap_virtual_claim_context(
        db_session,
        session,
        patient_id=patient.id,
        insurance_company_id=company.id,
        procedure_code="62323",
    )
    draft = ensure_virtual_claim_draft(db_session, session)
    response = recompute_virtual_claim(db_session, draft)

    assert response.policy_summary is None
    assert response.checklist.policy_medical_necessity.policy_link_id.status == "missing"
    assert response.checklist.policy_medical_necessity.policy_url.status == "missing"
    assert response.checklist.policy_medical_necessity.stored_rules_available.status == "missing"
    assert response.checklist.readiness.ready_to_draft is False
