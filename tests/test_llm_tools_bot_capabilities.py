from app.llm.tools import execute_tool
from app.llm.tools.registry import ToolContext


def _collect_tool_names(result: dict) -> set[str]:
    names: set[str] = set()
    for category in result.get("categories", []):
        for item in category.get("capabilities", []):
            names.add(item.get("tool"))
    return names


def test_get_bot_capabilities_all_includes_known_tools() -> None:
    ctx = ToolContext(db=None)  # type: ignore[arg-type]
    result = execute_tool("get_bot_capabilities", {"category": "all", "language": "en"}, ctx)

    names = _collect_tool_names(result)
    assert "get_bot_capabilities" in names
    assert "list_procedure_codes" in names
    assert "nonexistent_tool" not in names


def test_get_bot_capabilities_category_filter_system() -> None:
    ctx = ToolContext(db=None)  # type: ignore[arg-type]
    result = execute_tool("get_bot_capabilities", {"category": "system", "language": "en"}, ctx)

    names = _collect_tool_names(result)
    assert "get_bot_capabilities" in names
    assert "list_procedure_codes" not in names


def test_get_bot_capabilities_include_schema() -> None:
    ctx = ToolContext(db=None)  # type: ignore[arg-type]
    result = execute_tool(
        "get_bot_capabilities",
        {"category": "system", "language": "en", "include_schemas": True},
        ctx,
    )

    for category in result["categories"]:
        for item in category["capabilities"]:
            if item["tool"] == "get_bot_capabilities":
                assert "input_schema" in item
                assert "properties" in item["input_schema"]
                return
    raise AssertionError("get_bot_capabilities not found in response")


def test_get_bot_capabilities_invalid_category() -> None:
    ctx = ToolContext(db=None)  # type: ignore[arg-type]
    result = execute_tool(
        "get_bot_capabilities",
        {"category": "invalid", "language": "en"},
        ctx,
    )

    assert result["error"]["code"] == "TOOL_VALIDATION_ERROR"
