import uuid

import pytest
from pydantic import ValidationError

from app.db.models import Tenant, User
from app.llm.tools import execute_tool, list_tool_schemas, validate_tool_args
from app.llm.tools.registry import ToolContext


def test_tool_arg_validation_valid() -> None:
    args = {"patient_id": str(uuid.uuid4())}
    validated = validate_tool_args("get_patient", args)
    assert str(validated.patient_id) == args["patient_id"]


def test_tool_arg_validation_invalid() -> None:
    with pytest.raises(ValidationError):
        validate_tool_args("get_patient", {"patient_id": "bad"})


def test_unknown_tool_is_rejected() -> None:
    ctx = ToolContext(db=None, tenant_id=uuid.uuid4())  # type: ignore[arg-type]
    result = execute_tool("unknown_tool", {}, ctx)
    assert result["error"]["code"] == "UNKNOWN_TOOL"


def test_tool_schema_list_has_known_tools() -> None:
    tools = list_tool_schemas()
    names = {tool["function"]["name"] for tool in tools}
    assert "get_patient" in names
    assert "get_account" in names
    assert "time_now" in names


def test_time_now_tool() -> None:
    ctx = ToolContext(db=None, tenant_id=uuid.uuid4())  # type: ignore[arg-type]
    result = execute_tool("time_now", {"tz": "Asia/Tbilisi"}, ctx)
    assert result["tz"] == "Asia/Tbilisi"
    assert isinstance(result["now"], str)
    assert "T" in result["now"]
    assert "+" in result["now"] or "-" in result["now"]


def test_get_account_tool(db_session) -> None:
    tenant = Tenant(id=uuid.uuid4(), name="Tools Tenant")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="account@example.com",
        hashed_password="hashed",
        is_active=True,
    )
    db_session.add_all([tenant, user])
    db_session.commit()

    ctx = ToolContext(db=db_session, tenant_id=tenant.id, user_id=user.id)
    result = execute_tool("get_account", {}, ctx)
    assert result["email"] == "account@example.com"
    assert result["user_id"] == str(user.id)
