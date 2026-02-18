from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import AuditLog, Clinic, Claim, InsuranceCompany, Patient, User
from app.db.session import get_db
from app.llm.tools import ToolContext, execute_tool
from app.main import app
from app.services.audit import AuditContext, AuditLogger
from app.services.claims.ingestion import ingest_parsed_pdf
from app.utils.time import utcnow


def _fresh_session(db_session: Session) -> Session:
    bind = db_session.get_bind()
    return Session(bind=bind, expire_on_commit=False)


def _seed_clinic(db_session: Session, name: str) -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name=name, created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_user(db_session: Session, email: str, clinic_id: int, role: str = "doctor") -> User:
    user = User(
        id=next_id(db_session, User),
        email=email,
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=clinic_id,
        role=role,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    return user


def _seed_patient_and_insurer(db_session: Session, user: User) -> tuple[Patient, InsuranceCompany]:
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=user.clinic_id,
        first_name="Jane",
        last_name="Doe",
        created_at=utcnow(),
    )
    insurer = InsuranceCompany(
        id=next_id(db_session, InsuranceCompany),
        name="Test Insurance",
        created_at=utcnow(),
    )
    db_session.add_all([patient, insurer])
    db_session.commit()
    return patient, insurer


def test_claim_crud_audit_logs_and_request_id(db_session: Session) -> None:
    clinic = _seed_clinic(db_session, "Clinic A")
    user = _seed_user(db_session, "doctor@example.com", clinic_id=clinic.id)
    patient, insurer = _seed_patient_and_insurer(db_session, user)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        create_request_id = "req-claim-create"
        response = client.post(
            "/api/claims",
            json={
                "patient_id": patient.id,
                "insurance_company_id": insurer.id,
                "claim_status": "DRAFT",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-ID": create_request_id,
            },
        )
        assert response.status_code == 201
        claim_id = response.json()["id"]

        response = client.patch(
            f"/api/claims/{claim_id}",
            json={"claim_status": "PAID"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-ID": "req-claim-update",
            },
        )
        assert response.status_code == 200

        response = client.delete(
            f"/api/claims/{claim_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-ID": "req-claim-delete",
            },
        )
        assert response.status_code == 204

        with _fresh_session(db_session) as fresh:
            logs = (
                fresh.execute(
                    select(AuditLog).where(
                        AuditLog.entity == "claim",
                        AuditLog.entity_id == str(claim_id),
                    )
                )
                .scalars()
                .all()
            )
            actions = {log.action for log in logs}
            assert {"CREATE", "UPDATE", "DELETE"}.issubset(actions)
            create_log = next(log for log in logs if log.action == "CREATE")
            assert create_log.request_id == create_request_id
    finally:
        app.dependency_overrides.clear()


def test_pdf_ingest_creates_audit_log(db_session: Session) -> None:
    clinic = _seed_clinic(db_session, "Clinic Audit")
    user = _seed_user(db_session, "pdf@example.com", clinic_id=clinic.id)
    payload = {
        "pdf": {
            "user_info": {"name": "Test Patient", "date_of_birth": "01/01/1980"},
            "codes": [],
            "info": [
                {
                    "date": "01/01/2023",
                    "billed_amount": "100.00",
                    "allowed_amount": "80.00",
                    "paid_amount": "70.00",
                    "cpt": "99213",
                    "dx": ["M46.96"],
                    "reason_codes": [],
                }
            ],
        }
    }
    audit = AuditLogger(db_session, context=AuditContext(request_id="req-pdf"))

    result = ingest_parsed_pdf(payload=payload, current_user=user, db=db_session, audit_logger=audit)
    claim_id = result["claim_id"]

    with _fresh_session(db_session) as fresh:
        log = (
            fresh.execute(
                select(AuditLog).where(
                    AuditLog.action == "PDF_GENERATE",
                    AuditLog.entity == "claim",
                    AuditLog.entity_id == str(claim_id),
                )
            )
            .scalars()
            .first()
        )
        assert log is not None
        assert log.request_id == "req-pdf"


def test_llm_write_audit_logs(db_session: Session) -> None:
    clinic = _seed_clinic(db_session, "Clinic LLM")
    user = _seed_user(db_session, "llm@example.com", clinic_id=clinic.id)
    patient, insurer = _seed_patient_and_insurer(db_session, user)
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=user.id,
        clinic_id=user.clinic_id,
        patient_id=patient.id,
        insurance_company_id=insurer.id,
        claim_status="DRAFT",
        created_at=utcnow(),
    )
    db_session.add(claim)
    db_session.commit()

    ctx = ToolContext(
        db=db_session,
        user_id=user.id,
        clinic_id=user.clinic_id,
        role=user.role,
        request_id="req-ai",
    )
    proposed = execute_tool(
        "update_claim_fields",
        {"claim_id": claim.id, "patch": {"claim_status": "PAID"}, "confirm": False},
        ctx,
    )
    assert proposed.get("action_required") is True

    with _fresh_session(db_session) as fresh:
        proposed_log = (
            fresh.execute(
                select(AuditLog).where(
                    AuditLog.action == "AI_WRITE_PROPOSED",
                    AuditLog.entity == "claim",
                    AuditLog.entity_id == str(claim.id),
                )
            )
            .scalars()
            .first()
        )
        assert proposed_log is not None
        assert proposed_log.request_id == "req-ai"

    execute_tool(
        "update_claim_fields",
        {"claim_id": claim.id, "patch": {"claim_status": "PAID"}, "confirm": True},
        ctx,
    )

    with _fresh_session(db_session) as fresh:
        confirmed_log = (
            fresh.execute(
                select(AuditLog).where(
                    AuditLog.action == "AI_WRITE_CONFIRMED",
                    AuditLog.entity == "claim",
                    AuditLog.entity_id == str(claim.id),
                )
            )
            .scalars()
            .first()
        )
        assert confirmed_log is not None


def test_audit_log_clinic_isolation(db_session: Session) -> None:
    clinic_a = _seed_clinic(db_session, "Clinic A")
    clinic_b = _seed_clinic(db_session, "Clinic B")
    user_a = _seed_user(db_session, "a@example.com", clinic_id=clinic_a.id)
    user_b = _seed_user(db_session, "b@example.com", clinic_id=clinic_b.id)
    staff = _seed_user(
        db_session,
        "staff@example.com",
        clinic_id=clinic_a.id,
        role="platform_staff_admin",
    )

    audit_a = AuditLogger(db_session, context=AuditContext(request_id="req-a"))
    audit_a.log_event(
        action="CREATE",
        entity="claim",
        entity_id="1",
        actor=user_a,
        clinic_id=clinic_a.id,
    )
    audit_b = AuditLogger(db_session, context=AuditContext(request_id="req-b"))
    audit_b.log_event(
        action="CREATE",
        entity="claim",
        entity_id="2",
        actor=user_b,
        clinic_id=clinic_b.id,
    )

    token_a = create_access_token(str(user_a.id))
    token_staff = create_access_token(str(staff.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/clinic/audit-logs",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert response.status_code == 200
        rows = response.json()
        assert rows
        assert all(item["clinic_id"] == clinic_a.id for item in rows)

        response = client.get(
            "/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {token_staff}"},
        )
        assert response.status_code == 200
        rows = response.json()
        clinic_ids = {item["clinic_id"] for item in rows}
        assert clinic_a.id in clinic_ids
        assert clinic_b.id in clinic_ids
    finally:
        app.dependency_overrides.clear()
