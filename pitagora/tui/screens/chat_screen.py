"""ChatScreen: full-screen chat view with focused input box."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
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
        with Horizontal(id="workspace"):
            with Vertical(id="sidebar"):
                yield JourneyBarWidget(id="journey-bar")
                yield ConceptTreeWidget(id="concept-tree")
            with Vertical(id="main-panel"):
                yield MessageLogWidget(id="message-log")
                yield Input(
                    placeholder="Ask a question or type / for commands...",
                    id="chat-input",
                )
                yield CommandPaletteWidget(id="command-palette")
            with Vertical(id="inspector"):
                yield AgentStatusWidget(id="agent-status")
                yield TokenMeterWidget(id="token-meter")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#chat-input").focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        msg_log = self.query_one("#message-log", MessageLogWidget)
        msg_log.messages = list(msg_log.messages) + [{"role": "user", "content": text}]
