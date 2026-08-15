"""CommandPaletteWidget: slash command palette overlay."""

from textual.reactive import reactive
from textual.widgets import Static


class CommandPaletteWidget(Static):
    command_query: reactive[str] = reactive("")

    COMMANDS = [
        "/help - Show help overlay",
        "/mode <mode> - Switch study mode",
        "/topic <topic> - Change topic",
        "/model <model> - Change LLM model",
        "/explore <topic> - Start learning journey",
        "/verify <expr> - Verify math claim",
        "/research <query> - Web research",
        "/save - Save current session",
        "/sessions - List sessions",
        "/resume - Resume session",
        "/quit - Exit app",
    ]

    def render(self) -> str:
        matching = [
            c
            for c in self.COMMANDS
            if not self.command_query or self.command_query.lower() in c.lower()
        ]
        return "Slash Command Palette:\n" + "\n".join(f"  {c}" for c in matching[:8])
