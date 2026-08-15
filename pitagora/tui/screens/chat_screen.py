"""ChatScreen: full-screen chat view."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Input

from pitagora.tui.widgets import (
    AgentStatusWidget,
    CommandPaletteWidget,
    ConceptTreeWidget,
    JourneyBarWidget,
    MessageLogWidget,
    TokenMeterWidget,
)


class ChatScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield AgentStatusWidget(id="agent-status")
        yield TokenMeterWidget(id="token-meter")
        yield JourneyBarWidget(id="journey-bar")
        yield ConceptTreeWidget(id="concept-tree")
        yield MessageLogWidget(id="message-log")
        yield Input(placeholder="Ask a question or type / for commands...", id="chat-input")
        yield CommandPaletteWidget(id="command-palette")
        yield Footer()
