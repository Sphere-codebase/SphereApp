import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.db.id_utils import next_id
from app.db.models import (
    ChatSession,
    Claim,
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
from app.llm.tools import execute_tool, list_tool_schemas, validate_tool_args
from app.llm.tools.registry import ToolContext
from app.utils.time import utcnow


def test_tool_arg_validation_valid() -> None:
    args = {"patient_id": 123}
    validated = validate_tool_args("get_patient", args)
    assert validated.patient_id == args["patient_id"]


def test_tool_arg_validation_invalid() -> None:
    with pytest.raises(ValidationError):
        validate_tool_args("get_patient", {"patient_id": "bad"})


def test_unknown_tool_is_rejected() -> None:
    ctx = ToolContext(db=None)  # type: ignore[arg-type]
    result = execute_tool("unknown_tool", {}, ctx)
    assert result["error"]["code"] == "UNKNOWN_TOOL"


def test_tool_schema_list_has_known_tools() -> None:
    tools = list_tool_schemas()
    names = {tool["function"]["name"] for tool in tools}
    assert "get_patient" in names
    assert "get_account" in names
    assert "time_now" in names
    assert "get_virtual_claim" in names
    assert "update_virtual_claim" in names
    assert "evaluate_claim_readiness" in names
    assert "list_missing_claim_fields" in names
    assert "get_virtual_claim_checklist" in names
    assert "bootstrap_virtual_claim_context" in names
    assert "update_virtual_claim_fields" in names
    assert "propose_materialize_virtual_claim" in names


def test_time_now_tool() -> None:
    ctx = ToolContext(db=None)  # type: ignore[arg-type]
    result = execute_tool("time_now", {"tz": "Asia/Tbilisi"}, ctx)
    assert result["tz"] == "Asia/Tbilisi"
    assert isinstance(result["now"], str)
    assert "T" in result["now"]
    assert "+" in result["now"] or "-" in result["now"]


def test_get_account_tool(db_session) -> None:
    doctor_role = db_session.execute(
        Role.__table__.select().where(Role.code == "doctor")
    ).fetchone()
    if doctor_role is None:
        role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(role)
        db_session.flush()
        doctor_role_id = role.id
    else:
        doctor_role_id = doctor_role.id
    user = User(
        id=next_id(db_session, User),
        email="account@example.com",
        password_hash="hashed",
        is_active=True,
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role_id))
    db_session.commit()

    ctx = ToolContext(db=db_session, user_id=user.id)
    result = execute_tool("get_account", {}, ctx)
    assert result["email"] == "account@example.com"
    assert result["user_id"] == user.id


def test_claim_tools_include_patient_and_payer_names(db_session) -> None:
    doctor_role = db_session.execute(
        Role.__table__.select().where(Role.code == "doctor")
    ).fetchone()
    if doctor_role is None:
        role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(role)
        db_session.flush()
        doctor_role_id = role.id
    else:
        doctor_role_id = doctor_role.id
    user = User(
        id=next_id(db_session, User),
        email="claims@example.com",
        password_hash="hashed",
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
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=user.id,
        clinic_id=1,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_status="PAID",
        created_at=utcnow(),
    )
    db_session.add_all(
        [user, UserRole(user_id=user.id, role_id=doctor_role_id), company, patient, claim]
    )
    db_session.commit()

    ctx = ToolContext(db=db_session, user_id=user.id)
    listed = execute_tool("list_claims", {"patient_id": patient.id}, ctx)
    fetched = execute_tool("get_claim", {"claim_id": claim.id}, ctx)

    assert listed["claims"][0]["patient_name"] == "DAVID R WIENTZEN"
    assert listed["claims"][0]["insurance_company_name"] == "Aetna"
    assert fetched["claim"]["patient_name"] == "DAVID R WIENTZEN"
    assert fetched["claim"]["insurance_company_name"] == "Aetna"


def test_search_patients_matches_full_name_query(db_session) -> None:
    doctor_role = db_session.execute(
        Role.__table__.select().where(Role.code == "doctor")
    ).fetchone()
    if doctor_role is None:
        role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(role)
        db_session.flush()
        doctor_role_id = role.id
    else:
        doctor_role_id = doctor_role.id
    user = User(
        id=next_id(db_session, User),
        email="search@example.com",
        password_hash="hashed",
        is_active=True,
        clinic_id=1,
        created_at=utcnow(),
    )
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=1,
        first_name="DAVID R",
        last_name="WIENTZEN",
        created_at=utcnow(),
    )
    db_session.add_all([user, UserRole(user_id=user.id, role_id=doctor_role_id), patient])
    db_session.commit()

    ctx = ToolContext(db=db_session, user_id=user.id)
    result = execute_tool("search_patients", {"query": "DAVID R WIENTZEN"}, ctx)

    assert result["patients"]
    assert result["patients"][0]["id"] == patient.id


def test_virtual_claim_tools_bootstrap_and_materialize(db_session) -> None:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="virtual-tools@example.com",
        password_hash="hashed",
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
            '{"criteria": ["radiculopathy", "fluoroscopy", "physical therapy", '
            '"neuro exam", "radiologic findings", "mri", "session limit"]}'
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

    ctx = ToolContext(
        db=db_session,
        user_id=user.id,
        clinic_id=1,
        role="doctor",
        chat_session_id=session.id,
    )

    bootstrapped = execute_tool(
        "bootstrap_virtual_claim_context",
        {
            "patient_query": "DAVID WIENTZEN",
            "insurance_company_name": "Aetna",
            "procedure_code": "62323",
        },
        ctx,
    )
    assert bootstrapped["patient"]["name"] == "DAVID R WIENTZEN"
    assert bootstrapped["payer"]["name"] == "Aetna"
    assert bootstrapped["procedure"]["code"] == "62323"

    checklist = execute_tool("get_virtual_claim", {}, ctx)
    assert checklist["checklist"]["service"]["procedure_code"]["value"] == "62323"

    readiness = execute_tool("evaluate_claim_readiness", {}, ctx)
    assert readiness["ready_to_draft"] is False
    assert readiness["missing_fields"]

    updated = execute_tool(
        "update_virtual_claim",
        {
            "fields": [
                {"key": "service_date", "value": "2025-05-27"},
                {"key": "diagnosis.code", "value": "M54.16"},
                {"key": "clinical.radiculopathy", "value": True},
                {"key": "clinical.functional_limitation", "value": True},
                {"key": "clinical.conservative_treatment", "value": True},
                {"key": "clinical.imaging_guidance", "value": True},
                {"key": "clinical.neuro_exam", "value": True},
                {"key": "utilization.frequency_limit_ok", "value": True},
            ]
        },
        ctx,
    )
    assert updated["draft_id"] > 0

    missing = execute_tool("list_missing_claim_fields", {}, ctx)
    assert missing["missing_fields"]

    execute_tool(
        "update_virtual_claim",
        {
            "fields": [
                {"key": "clinical.radiology_consistency", "value": True},
                {"key": "clinical.mri_or_emg", "value": True},
            ]
        },
        ctx,
    )
    readiness = execute_tool("evaluate_claim_readiness", {}, ctx)
    assert readiness["ready_to_draft"] is True
    proposal = execute_tool("propose_materialize_virtual_claim", {}, ctx)
    assert proposal["action_required"] is True
    assert proposal["proposal"]["summary"]["procedure_code"] == "62323"


def test_create_claim_draft_is_blocked_until_virtual_claim_is_ready(db_session) -> None:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="virtual-guard@example.com",
        password_hash="hashed",
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
        [
            user,
            UserRole(user_id=user.id, role_id=doctor_role.id),
            company,
            patient,
            mcp,
            session,
        ]
    )
    db_session.commit()

    ctx = ToolContext(
        db=db_session,
        user_id=user.id,
        clinic_id=1,
        role="doctor",
        chat_session_id=session.id,
    )

    execute_tool(
        "bootstrap_virtual_claim_context",
        {
            "patient_id": patient.id,
            "insurance_company_id": company.id,
            "procedure_code": "62323",
        },
        ctx,
    )

    result = execute_tool(
        "create_claim_draft",
        {
            "patient_id": patient.id,
            "fields": {
                "insurance_company_id": company.id,
                "service_date": "2025-05-27",
            },
        },
        ctx,
    )

    assert result["error"]["code"] == "VIRTUAL_CLAIM_NOT_READY"
