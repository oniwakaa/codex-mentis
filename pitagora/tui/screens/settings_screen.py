"""SettingsScreen: dynamic configuration view."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from pitagora.core.config import load_config


class SettingsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._build_settings_content(), id="settings-content")
        yield Footer()

    def on_screen_resume(self) -> None:
        static = self.query_one("#settings-content", Static)
        static.update(self._build_settings_content())

    def _build_settings_content(self) -> str:
        cfg = load_config()
        lines = [
            "⚙️ [bold cyan]Pitagora Active Configuration[/bold cyan]\n",
            f"  • [bold]Default Model:[/bold] {cfg.model or cfg.providers.default}",
            f"  • [bold]Math Sandbox:[/bold] {cfg.math.sandbox} (Plot Backend: {cfg.math.plot_backend})",
            f"  • [bold]Memory Backend:[/bold] {cfg.memory.backend} (Spaced Repetition: {cfg.memory.spaced_repetition})",
            f"  • [bold]UI Theme:[/bold] {cfg.ui.theme} (LaTeX Rendering: {cfg.ui.latex})",
            f"  • [bold]MCP EverMemOS:[/bold] {cfg.mcp.evermemos}",
            "\n[dim]To modify settings, use `pitagora config set <key> <value>` or edit ~/.pitagora/config.yaml[/dim]",
        ]
        return "\n".join(lines)
