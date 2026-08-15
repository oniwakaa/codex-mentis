import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pitagora.agents.base import validate_json_schema
from pitagora.agents.permissions import Permission, PermissionManager


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict  # JSON Schema
    required_permission: str  # "read" | "write" | "admin"
    category: str  # "file" | "web" | "math" | "memory" | "agent"
    handler: Callable[..., Any]


_PERM_MAP = {
    "read": Permission.READONLY,
    "readonly": Permission.READONLY,
    "write": Permission.READWRITE,
    "readwrite": Permission.READWRITE,
    "admin": Permission.ADMIN,
}


class ToolRegistry:
    def __init__(self, permission_manager: PermissionManager | None = None):
        self._tools: dict[str, ToolSpec] = {}
        self.permission_manager = permission_manager or PermissionManager(Permission.ADMIN)

    def register(self, spec: ToolSpec) -> None:
        """Register a tool specification."""
        if spec.name in self._tools:
            raise ValueError(f"Tool '{spec.name}' already registered")
        self._tools[spec.name] = spec

    def get_schemas(self, permission_level: str = "read") -> list[dict]:
        """Return JSON Schema array for tools at or below permission_level."""
        levels = {"read": 0, "write": 1, "admin": 2}
        max_level = levels.get(permission_level, 0)
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
            }
            for spec in self._tools.values()
            if levels.get(spec.required_permission, 0) <= max_level
        ]

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name with validated arguments."""
        if tool_name not in self._tools:
            return {"error": f"Unknown tool: {tool_name}"}
        spec = self._tools[tool_name]

        req_perm = _PERM_MAP.get(spec.required_permission.lower(), Permission.READONLY)
        permitted = await self.permission_manager.check(req_perm, f"Execute tool {tool_name}")
        if not permitted:
            return {"error": f"Permission denied for tool: {tool_name}"}

        if spec.input_schema:
            errors = validate_json_schema(spec.input_schema, arguments)
            if errors:
                return {"error": f"Validation failed: {', '.join(errors)}"}

        try:
            res = spec.handler(**arguments)
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                res = await res
            return {"tool_name": tool_name, "result": res, "error": None}
        except Exception as e:
            return {"tool_name": tool_name, "result": None, "error": str(e)}
