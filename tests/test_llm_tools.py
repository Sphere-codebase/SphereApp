import uuid

import pytest
from pydantic import ValidationError

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
