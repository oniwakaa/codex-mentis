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
        
        progress = context.get("progress", 0.0)
        progress_bar = ProgressBar(total=100, completed=int(progress * 100))
        
        table.add_row("Progress", progress_bar)
        
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
                # Check for textual's RichVisual which wraps Rich renderables
                renderable = getattr(child, "renderable", child.render())
                
                # If it's a RichVisual, unwrap the actual renderable
                if hasattr(renderable, "_renderable"):
                    renderable = renderable._renderable
                
                if hasattr(renderable, "plain"):
                    text += renderable.plain + "\n"
                elif isinstance(renderable, str):
                    text += renderable + "\n"
                else:
                    # Catch Panels and other rich renderables that might not have plain directly
                    from rich.console import Console
                    console = Console()
                    with console.capture() as capture:
                        console.print(renderable)
                    text += capture.get() + "\n"
        return text



import re
from typing import List, Tuple
from pitagora.latex_render import latex_to_unicode
from textual.message import Message
from textual import events
from textual.widgets import OptionList
from pitagora.cli.repl_input import COMMAND_TREE

class InputHistory:
    def __init__(self, limit: int = 100):
        self.limit = limit
        self.items: list[str] = []
        self.cursor = 0
        
    def add(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self.items and self.items[-1] == text:
            pass
        else:
            self.items.append(text)
            
        if len(self.items) > self.limit:
            self.items.pop(0)
            
        self.cursor = len(self.items)
        
    def previous(self) -> str:
        if not self.items:
            return ""
        if self.cursor > 0:
            self.cursor -= 1
            return self.items[self.cursor]
        return self.items[0] if self.items else ""
        
    def next(self) -> str:
        if not self.items:
            return ""
        if self.cursor < len(self.items) - 1:
            self.cursor += 1
            return self.items[self.cursor]
        self.cursor = len(self.items)
        return ""


def split_math(text: str) -> List[Tuple[str, str, int]]:
    parts = []
    eq_num = 1
    
    # regex to find non-overlapping $$...$$ blocks
    import re
    pattern = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
    
    last_end = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_end:
            # markdown part
            md_text = text[last_end:start]
            # Replace inline math $...$ first before parsing with latex_to_unicode
            md_text = re.sub(r"\$([^$]+)\$", lambda m: latex_to_unicode(m.group(1)), md_text)
            parts.append(("markdown", md_text, 0))
            
        # equation part
        eq_text = match.group(1).strip()
        parts.append(("equation", eq_text, eq_num))
        eq_num += 1
        
        last_end = end
        
    if last_end < len(text):
        md_text = text[last_end:]
        # Replace inline math $...$ first before parsing with latex_to_unicode
        md_text = re.sub(r"\$([^$]+)\$", lambda m: latex_to_unicode(m.group(1)), md_text)
        parts.append(("markdown", md_text, 0))
        
    return [p for p in parts if p[1]] if parts else []


class CommandPopup(OptionList):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for cmd in COMMAND_TREE:
            self.add_option(cmd)


class ChatTextArea(TextArea):
    BINDINGS = [
        Binding("ctrl+x", "app.toggle_compact", "Compact", show=False),
        Binding("ctrl+b", "app.toggle_sidebar", "Sidebar", show=False),
        Binding("ctrl+l", "app.clear_visible", "Clear", show=False),
    ]
    
    class Submitted(Message):
        def __init__(self, text_area, text: str) -> None:
            self.text_area = text_area
            self.text = text
            super().__init__()
            
    class AutocompleteRequested(Message):
        def __init__(self, text_area, accept: bool = False) -> None:
            self.text_area = text_area
            self.accept = accept
            super().__init__()
            
    class AutocompleteNavigate(Message):
        def __init__(self, text_area, direction: str) -> None:
            self.text_area = text_area
            self.direction = direction
            super().__init__()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_history = InputHistory()

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "shift+enter":
            self.insert("\n")
            event.prevent_default()
            return
        if event.key == "enter":
            text = self.text
            if text.strip():
                self.post_message(self.Submitted(self, text))
            event.prevent_default()
            return
        if event.key == "tab":
            self.post_message(self.AutocompleteRequested(self, accept=True))
            event.prevent_default()
            return
            
        teaching = False
        try:
            if hasattr(self.app, "controller") and hasattr(self.app.controller, "context"):
                teaching = self.app.controller.context.get("teaching", False)
        except Exception:
            pass
            
        if teaching and not self.text:
            if event.character in {"n", "e", "d", "s", "?", "v", "q", "p"}:
                self.post_message(self.Submitted(self, event.character))
                event.prevent_default()
                return

        if event.key in {"up", "down"}:
            from textual.css.query import NoMatches
            popup = None
            try:
                popup = self.app.query_one("#command-popup")
            except NoMatches:
                pass
                
            if popup and popup.display:
                self.post_message(self.AutocompleteNavigate(self, event.key))
                event.prevent_default()
                return
                
            cursor_row, _ = self.cursor_location
            doc_lines = self.document.line_count
            
            if event.key == "up" and cursor_row == 0:
                self.text = self.input_history.previous()
                self.move_cursor((self.document.line_count - 1, len(self.document.get_line(self.document.line_count - 1))))
                event.prevent_default()
                return
            elif event.key == "down" and cursor_row == doc_lines - 1:
                self.text = self.input_history.next()
                self.move_cursor((self.document.line_count - 1, len(self.document.get_line(self.document.line_count - 1))))
                event.prevent_default()
                return

        await super()._on_key(event)

