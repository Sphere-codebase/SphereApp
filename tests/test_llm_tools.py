import pytest
from pydantic import ValidationError

from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole
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
