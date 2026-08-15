import pytest

from pitagora.agents.tools.builtin import register_builtin_tools
from pitagora.agents.tools.registry import ToolRegistry, ToolSpec


def test_tool_registry_register_and_get_schemas():
    registry = ToolRegistry()

    def dummy_handler(x: int) -> int:
        return x * 2

    spec = ToolSpec(
        name="dummy",
        description="Dummy tool",
        input_schema={
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
        },
        required_permission="read",
        category="math",
        handler=dummy_handler,
    )

    registry.register(spec)
    schemas = registry.get_schemas("read")
    assert len(schemas) == 1
    assert schemas[0]["name"] == "dummy"

    # Duplicate registration raises ValueError
    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)


def test_tool_registry_permission_filtering():
    registry = ToolRegistry()
    register_builtin_tools(registry)

    read_schemas = registry.get_schemas("read")
    write_schemas = registry.get_schemas("write")
    admin_schemas = registry.get_schemas("admin")

    assert len(read_schemas) < len(write_schemas)
    assert len(write_schemas) < len(admin_schemas)
    assert len(admin_schemas) >= 10


@pytest.mark.asyncio
async def test_tool_registry_execute_success():
    registry = ToolRegistry()

    async def add(a: int, b: int) -> dict:
        return {"sum": a + b}

    spec = ToolSpec(
        name="add",
        description="Add numbers",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
        required_permission="read",
        category="math",
        handler=add,
    )

    registry.register(spec)
    res = await registry.execute("add", {"a": 5, "b": 7})
    assert res["error"] is None
    assert res["result"] == {"sum": 12}


@pytest.mark.asyncio
async def test_tool_registry_execute_validation_error():
    registry = ToolRegistry()

    spec = ToolSpec(
        name="add",
        description="Add numbers",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
        required_permission="read",
        category="math",
        handler=lambda a, b: {"sum": a + b},
    )

    registry.register(spec)
    res = await registry.execute("add", {"a": 5})
    assert res.get("error") is not None
    assert "Validation failed" in res["error"]


@pytest.mark.asyncio
async def test_tool_registry_execute_unknown_tool():
    registry = ToolRegistry()
    res = await registry.execute("nonexistent", {})
    assert res["error"] == "Unknown tool: nonexistent"


@pytest.mark.asyncio
async def test_builtin_tools_execution(temp_db):
    registry = ToolRegistry()
    register_builtin_tools(registry)

    # Test evaluate_expression builtin tool
    eval_res = await registry.execute("evaluate_expression", {"expression": "2 + 3"})
    assert eval_res["error"] is None
    assert eval_res["result"]["verified"] is True
    assert "5" in str(eval_res["result"]["value"])

    # Test plot_function builtin tool
    plot_res = await registry.execute("plot_function", {"expression": "x**2"})
    assert plot_res["error"] is None
    assert plot_res["result"]["status"] == "plotted"
