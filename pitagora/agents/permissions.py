from collections.abc import Awaitable, Callable
from enum import IntEnum


class Permission(IntEnum):
    READONLY = 0
    READWRITE = 1
    ADMIN = 2


class PermissionManager:
    """5-level escalation: ReadOnly → ReadWrite → Admin → Prompt → Allow

    Logic: if current >= required: allow
            elif one_level_gap: ask_user (prompt)
            else: deny
    """

    def __init__(self, default_level: Permission = Permission.READWRITE):
        self.current_level = default_level
        self._ask_user: Callable[[str], Awaitable[bool]] | None = None

    def set_user_callback(self, callback: Callable[[str], Awaitable[bool]]) -> None:
        """Set the function that prompts the user for permission."""
        self._ask_user = callback

    async def check(self, required: Permission, action_desc: str = "") -> bool:
        """Check if an action is permitted under current permission level."""
        if self.current_level >= required:
            return True

        gap = required - self.current_level
        if gap == 1 and self._ask_user:
            return await self._ask_user(action_desc)

        return False
