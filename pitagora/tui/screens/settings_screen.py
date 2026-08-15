"""SettingsScreen: configuration view."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


class SettingsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "⚙️ Pitagora Settings\n\nDefault Model: gpt-4o\nFallback Providers: anthropic, ollama\nMax Iterations: 25\nMax Budget USD: $2.00",
            id="settings-content",
        )
        yield Footer()
