from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import Claim, Clinic, InsuranceCompany, McpCode, Patient, Role, User, UserRole
from app.llm.tools import execute_tool
from app.llm.tools.registry import ToolContext
from app.services.claims.normalization import normalize_procedure_code
from app.utils.time import utcnow


def _ensure_doctor_role(db_session: Session) -> Role:
    role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if role is None:
        role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(role)
        db_session.flush()
    return role


def _seed_clinic(db_session: Session, name: str) -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name=name, created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_doctor(db_session: Session, email: str, clinic_id: int = 1) -> User:
    role = _ensure_doctor_role(db_session)
    user = User(
        id=next_id(db_session, User),
        email=email,
        password_hash="hashed",
        is_active=True,
        clinic_id=clinic_id,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()
    return user


def _seed_claim(db_session: Session, doctor: User) -> Claim:
    company = InsuranceCompany(
        id=next_id(db_session, InsuranceCompany), name=f"Company {doctor.id}"
    )
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=doctor.id,
        clinic_id=doctor.clinic_id,
        first_name="Jane",
        last_name="Doe",
        created_at=utcnow(),
    )
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=doctor.id,
        clinic_id=doctor.clinic_id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_status="DRAFT",
        created_at=utcnow(),
    )
    db_session.add_all([company, patient, claim])
    db_session.commit()
    return claim


def test_list_procedure_codes_respects_limit(db_session: Session) -> None:
    db_session.add_all(
        [
            McpCode(code="10001", description="Code B"),
            McpCode(code="10000", description="Code A"),
            McpCode(code="10002", description="Code C"),
        ]
    )
    db_session.commit()

    ctx = ToolContext(db=db_session)
    result = execute_tool("list_procedure_codes", {"limit": 2}, ctx)

    assert result["count"] == 2
    assert [item["code"] for item in result["items"]] == ["10000", "10001"]


def test_normalize_procedure_code_common_variants() -> None:
    assert normalize_procedure_code("62323") == "62323"
    assert normalize_procedure_code("CPT 62323") == "62323"
    assert normalize_procedure_code("CPT62323") == "62323"
    assert normalize_procedure_code("CTP 62323") == "62323"
    assert normalize_procedure_code("СТP 62323") == "62323"
    assert normalize_procedure_code("code: 62323.") == "62323"


def test_get_procedure_code_normalizes_common_cpt_variants(db_session: Session) -> None:
    db_session.add(
        McpCode(
            code="62323",
            description="Injection(s), of diagnostic or therapeutic substance(s)",
        )
    )
    db_session.commit()

    ctx = ToolContext(db=db_session)
    result = execute_tool("get_procedure_code", {"code": "CPT62323"}, ctx)

    assert result["exists"] is True
    assert result["code"] == "62323"


def test_get_procedure_code_unknown_returns_exists_false(db_session: Session) -> None:
    ctx = ToolContext(db=db_session)
    result = execute_tool("get_procedure_code", {"code": "99999"}, ctx)

    assert result["exists"] is False
    assert result["description"] is None


def test_explain_coverage_for_code_claim_isolation(db_session: Session) -> None:
    clinic_a = _seed_clinic(db_session, "Clinic A")
    clinic_b = _seed_clinic(db_session, "Clinic B")
    doctor_a = _seed_doctor(db_session, "doctor-a@example.com", clinic_id=clinic_a.id)
    doctor_b = _seed_doctor(db_session, "doctor-b@example.com", clinic_id=clinic_b.id)
    claim = _seed_claim(db_session, doctor_a)

    ctx = ToolContext(db=db_session, user_id=doctor_b.id, clinic_id=doctor_b.clinic_id)
    result = execute_tool(
        "explain_coverage_for_code",
        {"code": "27096", "claim_id": claim.id},
        ctx,
    )

    assert result["error"]["code"] == "NOT_FOUND"
