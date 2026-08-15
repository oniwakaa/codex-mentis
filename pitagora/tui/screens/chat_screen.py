"""ChatScreen: full-screen chat view with interactive controller dispatch."""

from textual import work
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

    def on_input_changed(self, event: Input.Changed) -> None:
        palette = self.query_one("#command-palette", CommandPaletteWidget)
        if event.value.startswith("/"):
            palette.command_query = event.value
            palette.styles.display = "block"
        else:
            palette.styles.display = "none"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        palette = self.query_one("#command-palette", CommandPaletteWidget)
        palette.styles.display = "none"
        self.process_user_input(text)

    @work(exclusive=True, thread=True)
    def process_user_input(self, text: str) -> None:
        app = self.app
        controller = getattr(app, "controller", None)
        if not controller:
            return

        msg_log = self.query_one("#message-log", MessageLogWidget)
        status_widget = self.query_one("#agent-status", AgentStatusWidget)

        for event in controller.handle_input(text):
            if event.kind == "user":
                msg_log.messages = list(msg_log.messages) + [
                    {"role": "user", "content": str(event.content)}
                ]
            elif event.kind in ("markdown", "text", "renderable"):
                msg_log.messages = list(msg_log.messages) + [
                    {"role": "assistant", "content": str(event.content)}
                ]
            elif event.kind == "error":
                msg_log.messages = list(msg_log.messages) + [
                    {"role": "system", "content": f"Error: {event.content}"}
                ]
            elif event.kind == "status":
                status_widget.agent_name = str(event.content)
                msg_log.messages = list(msg_log.messages) + [
                    {"role": "system", "content": str(event.content)}
                ]
            elif event.kind == "state_changed":
                msg_count = getattr(controller, "message_count", 0)
                status_widget.tokens = msg_count * 15
                status_widget.cost_usd = msg_count * 0.002
