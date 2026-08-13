from typing import Any, Dict

from rich.progress import ProgressBar
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea


class ContextSidebar(Static):
    def update_context(self, context: Dict[str, Any]) -> None:
        table = Table.grid(expand=True)
        table.add_column()
        table.add_column(justify="right")
        table.add_row("Mode", context.get("mode", ""))
        table.add_row("Topic", context.get("topic", ""))
        table.add_row("Model", context.get("model", ""))
        table.add_row("Messages", str(context.get("message_count", 0)))
        
        self.update(table)


class SidebarScreen(ModalScreen):
    def __init__(self, context: Dict[str, Any]):
        super().__init__()
        self.context = context

    def compose(self) -> ComposeResult:
        sidebar = ContextSidebar(id="modal-sidebar")
        yield sidebar
        
    def on_mount(self) -> None:
        sidebar = self.query_one(ContextSidebar)
        sidebar.update_context(self.context)

    def on_click(self) -> None:
        self.dismiss()


class QuitScreen(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        yield Static("Are you sure you want to quit?", id="quit-message")
        yield Button("Quit", variant="error", id="quit")
        yield Button("Cancel", variant="primary", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.dismiss(True)
        else:
            self.dismiss(False)


class Conversation(VerticalScroll):
    @property
    def renderable_text(self) -> str:
        text = ""
        for child in self.children:
            if isinstance(child, Static):
                rendered = child.render()
                if hasattr(rendered, "plain"):
                    text += rendered.plain + "\n"
                elif isinstance(rendered, str):
                    text += rendered + "\n"
        return text


class ChatTextArea(TextArea):
    BINDINGS = [
        Binding("ctrl+x", "app.toggle_compact", "Compact", show=False),
        Binding("ctrl+b", "app.toggle_sidebar", "Sidebar", show=False),
        Binding("ctrl+l", "app.clear_visible", "Clear", show=False),
    ]
