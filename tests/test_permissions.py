import pytest

from pitagora.agents.permissions import Permission, PermissionManager
from pitagora.agents.tools.registry import ToolRegistry, ToolSpec


@pytest.mark.asyncio
async def test_permission_allow_within_level():
    pm = PermissionManager(default_level=Permission.READWRITE)
    assert await pm.check(Permission.READONLY) is True
    assert await pm.check(Permission.READWRITE) is True


@pytest.mark.asyncio
async def test_permission_prompt_one_level_gap():
    pm = PermissionManager(default_level=Permission.READWRITE)  # 1 level below ADMIN (2)

    prompt_calls = []

    async def mock_user_prompt(action_desc: str) -> bool:
        prompt_calls.append(action_desc)
        return True

    pm.set_user_callback(mock_user_prompt)

    # Required ADMIN (2), current READWRITE (1) -> gap is 1 -> prompts user
    allowed = await pm.check(Permission.ADMIN, "Delete database")
    assert allowed is True
    assert len(prompt_calls) == 1
    assert prompt_calls[0] == "Delete database"


@pytest.mark.asyncio
async def test_permission_deny_larger_gap():
    pm = PermissionManager(default_level=Permission.READONLY)  # 0 (READONLY)

    prompt_calls = []

    async def mock_user_prompt(action_desc: str) -> bool:
        prompt_calls.append(action_desc)
        return True

    pm.set_user_callback(mock_user_prompt)

    # Required ADMIN (2), current READONLY (0) -> gap is 2 -> denied without prompting
    allowed = await pm.check(Permission.ADMIN, "Admin action")
    assert allowed is False
    assert len(prompt_calls) == 0


@pytest.mark.asyncio
async def test_tool_registry_permission_integration():
    pm = PermissionManager(default_level=Permission.READONLY)
    registry = ToolRegistry(permission_manager=pm)

    prompt_calls = []

    async def mock_prompt(action: str) -> bool:
        prompt_calls.append(action)
        return True

    pm.set_user_callback(mock_prompt)

    spec_write = ToolSpec(
        name="write_tool",
        description="Write tool",
        input_schema={},
        required_permission="write",
        category="memory",
        handler=lambda: {"status": "ok"},
    )
    spec_admin = ToolSpec(
        name="admin_tool",
        description="Admin tool",
        input_schema={},
        required_permission="admin",
        category="agent",
        handler=lambda: {"status": "ok"},
    )

    registry.register(spec_write)
    registry.register(spec_admin)

    # Write tool has gap of 1 (READONLY -> READWRITE) -> triggers prompt, allowed
    res_write = await registry.execute("write_tool", {})
    assert res_write.get("error") is None
    assert len(prompt_calls) == 1

    # Admin tool has gap of 2 (READONLY -> ADMIN) -> denied
    res_admin = await registry.execute("admin_tool", {})
    assert res_admin.get("error") == "Permission denied for tool: admin_tool"
