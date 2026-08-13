
from typing import Optional, Dict, Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Static, OptionList
from textual import work
from pitagora.chat_controller import ChatEvent
from pitagora.cli.tui_widgets import split_math, EquationWidget
from pitagora.teaching.ui import build_comprehension_gauge, build_subconcept_progress, build_controls
from textual.widgets import Markdown


from pitagora.cli.repl_input import COMMAND_TREE
from pitagora.cli.tui_widgets import (
    ChatTextArea,
    ContextSidebar,
    Conversation,
    QuitScreen,
    SidebarScreen,
    CommandPopup,
)


class PitagoraApp(App):
    CSS = """
    PitagoraApp {
        layout: vertical;
    }
    
    #header, #footer {
        height: 1;
        background: $primary-background;
        color: $text;
        layout: horizontal;
    }

    #header {
        dock: top;
        background: #1a1a2e; /* deep-indigo */
        color: white;
    }

    #footer {
        dock: bottom;
        background: #1a1a2e; /* deep-indigo */
        color: white;
    }

    #brand {
        width: auto;
        padding: 0 1;
        color: gold;
    }

    #header-context {
        width: 1fr;
        content-align: right middle;
        padding: 0 1;
    }

    #main {
        height: 1fr;
        layout: horizontal;
    }

    #conversation {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }

    #sidebar {
        width: 28;
        height: 1fr;
        dock: right;
        border-left: solid $primary;
        padding: 1;
    }

    #input-container {
        height: auto;
        dock: bottom;
        border-top: solid $primary;
        layout: vertical;
    }
    
    #command-popup {
        display: none;
        height: auto;
        max-height: 10;
        border: solid $secondary;
        background: $surface;
    }

    #input-area {
        height: 4;
        layout: horizontal;
    }

    #prompt {
        width: 13;
        content-align: center middle;
        color: #00ffff; /* cyan */
    }

    #composer {
        width: 1fr;
        height: 1fr;
    }
    
    .compact #sidebar {
        display: none;
    }
    
    .compact #input-area {
        height: 2;
    }
    """

    BINDINGS = [
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=False),
        Binding("ctrl+l", "clear_visible", "Clear", show=False),
        Binding("ctrl+x", "toggle_compact", "Compact", show=False),
        Binding("escape", "request_quit", "Quit", show=False),
        Binding("ctrl+c", "request_quit", "Quit", show=False),
    ]

    def __init__(self, controller: Any, **kwargs):
        super().__init__(**kwargs)
        self.controller = controller
        self.active_journeys = []
        self._turn_worker = None
        self.due_reviews = []

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static("△ PITAGORA", id="brand"),
            Static(id="header-context"),
            id="header",
        )
        with Horizontal(id="main"):
            yield Conversation(id="conversation")
            yield ContextSidebar(id="sidebar")
            
        with Static(id="input-container"):
            yield CommandPopup(id="command-popup")
            with Horizontal(id="input-area"):
                yield Static("△ pitagora>", id="prompt")
                yield ChatTextArea(id="composer")
                
        yield Static(
            "Ctrl+B sidebar  Ctrl+X compact  / commands",
            id="footer",
        )

    def on_mount(self) -> None:
        conversation = self.query_one("#conversation", Conversation)
        
        banner_text = (
            "[bold #ffd700]    △[/]\n"
            "[bold #ffd700]   △ △[/]\n"
            "[bold #ffd700]  △   △[/]\n"
            "[bold #ffd700] △     △[/]\n"
            "[bold #ffd700]△ △ △ △ △[/]\n"
            "[bold #ffd700]PITAGORA[/]"
        )
        from rich.panel import Panel
        from pitagora.journeys.store import list_journeys
        
        journeys = list_journeys()
        active_count = len([j for j in journeys if j.get("status") == "active"])
        
        welcome_text = f"{banner_text}\n\nThink. Prove. Understand.\n\nActive Journeys: {active_count}"
        
        conversation.mount(Static(Panel(welcome_text, title="Welcome to Pitagora", border_style="gold1"), id="welcome-panel"))
        
        due_reviews = self.controller.context.get("due_reviews")
        if due_reviews:
            self.due_reviews = due_reviews
            conversation.mount(Static(f"Due Reviews: {self.due_reviews}", id="due-reviews-panel"))
            
        self.query_one("#composer").focus()
        self.set_interval(1, self._refresh_elapsed)
        
        sidebar = self.query_one("#sidebar", ContextSidebar)
        sidebar.update_context(self.controller.context)
        
        self.query_one("#command-popup").display = False

    def on_resize(self, event) -> None:
        self._apply_sidebar_layout(event.size.width)

    def _apply_sidebar_layout(self, width: int) -> None:
        sidebar = self.query_one("#sidebar", ContextSidebar)
        if width < 100 or self.has_class("compact"):
            sidebar.display = False
        else:
            sidebar.display = True

    def action_toggle_sidebar(self) -> None:
        if self.has_class("compact"):
            return
            
        sidebar = self.query_one("#sidebar", ContextSidebar)
        if self.size.width >= 100:
            sidebar.display = not sidebar.display
        else:
            self.push_screen(SidebarScreen(self.controller.context))

    def action_toggle_compact(self) -> None:
        self.toggle_class("compact")
        self._apply_sidebar_layout(self.size.width)

    def _quit_callback(self, confirm: bool) -> None:
        if confirm:
            if self._turn_worker and self._turn_worker.is_running:
                self._turn_worker.cancel()
            self.exit()

    async def action_request_quit(self) -> None:
        if self.controller.context.get("teaching"):
            self.push_screen(QuitScreen(), self._quit_callback)
        else:
            if self._turn_worker and self._turn_worker.is_running:
                self._turn_worker.cancel()
            self.exit()
            
    def action_clear_visible(self) -> None:
        conversation = self.query_one("#conversation")
        conversation.remove_children()
        conversation.mount(Static("[dim]Conversation cleared visually.[/dim]"))
        self.query_one("#composer").focus()


    @work(thread=True, exclusive=True, group="chat-turn")
    def run_turn(self, text: str) -> None:
        try:
            for event in self.controller.handle_input(text):
                self.call_from_thread(self.render_event, event)
        except Exception as exc:
            self.call_from_thread(
                self.render_event,
                ChatEvent("error", f"Error: {exc}"),
            )
        finally:
            self.call_from_thread(self.finish_turn)

    def finish_turn(self) -> None:
        composer = self.query_one("#composer")
        composer.read_only = False
        footer = self.query_one("#footer", Static)
        footer.update("Ctrl+B sidebar  Ctrl+X compact  / commands")
        composer.focus()
        conversation = self.query_one("#conversation")
        conversation.scroll_end(animate=False)

    def render_event(self, event: ChatEvent) -> None:
        conversation = self.query_one("#conversation")
        if event.kind == "user":
            conversation.mount(Static(f"[dim]△ you>[/dim] {event.content}", classes="user-msg"))
        elif event.kind == "markdown":
            parts = split_math(event.content)
            for p_type, p_text, _ in parts:
                if p_type == "markdown":
                    conversation.mount(Markdown(p_text, classes="markdown-msg"))
                elif p_type == "equation":
                    conversation.mount(EquationWidget(p_text, classes="equation-msg"))
        elif event.kind == "renderable":
            conversation.mount(Static(event.content, expand=True))
        elif event.kind == "error":
            conversation.mount(Static(f"[red]{event.content}[/red]", classes="error-msg"))
        elif event.kind == "status":
            if event.metadata.get("busy"):
                footer = self.query_one("#footer", Static)
                footer.update(f"[cyan]{event.content}[/cyan]")
            else:
                conversation.mount(Static(f"[dim]{event.content}[/dim]"))
        elif event.kind == "comprehension":
            conversation.mount(Static(build_comprehension_gauge(event.content)))
        elif event.kind == "subconcepts":
            conversation.mount(Static(build_subconcept_progress(event.content, event.metadata["current_index"], compact=True)))
        elif event.kind == "controls":
            conversation.mount(Static(build_controls()))
        elif event.kind == "state_changed":
            header_context = self.query_one("#header-context", Static)
            self._refresh_elapsed()
            sidebar = self.query_one("#sidebar", ContextSidebar)
            sidebar.update_context(event.metadata["context"])
            if event.metadata.get("quit"):
                self.exit()

    def _refresh_elapsed(self) -> None:
        elapsed = self.controller.context.get("elapsed_seconds", 0)
        minutes = elapsed // 60
        seconds = elapsed % 60
        header_context = self.query_one("#header-context", Static)
        header_context.update(f"{minutes:02d}:{seconds:02d}")
        

    def on_text_area_changed(self, event: ChatTextArea.Changed) -> None:
        composer = self.query_one("#composer")
        popup = self.query_one("#command-popup")
        if event.text_area == composer:
            text = composer.text
            if text.startswith("/") and " " not in text:
                text_lower = text.lower()
                popup.clear_options()
                
                # Add only matching commands
                has_matches = False
                for cmd in COMMAND_TREE:
                    if cmd.startswith(text_lower):
                        popup.add_option(cmd)
                        has_matches = True
                        
                if has_matches:
                    popup.display = True
                    popup.highlighted = 0
                else:
                    popup.display = False
            else:
                popup.display = False

                
    def on_chat_text_area_autocomplete_navigate(self, event: ChatTextArea.AutocompleteNavigate) -> None:
        popup = self.query_one("#command-popup")
        if popup.display:
            if event.direction == "up":
                popup.action_cursor_up()
            elif event.direction == "down":
                popup.action_cursor_down()

    def on_chat_text_area_autocomplete_requested(self, event: ChatTextArea.AutocompleteRequested) -> None:
        popup = self.query_one("#command-popup")
        if not event.accept:
            popup.display = False
            return
        if popup.display and popup.highlighted is not None:
            composer = self.query_one("#composer")
            option = popup.get_option_at_index(popup.highlighted)
            composer.text = str(option.prompt)
            composer.move_cursor((composer.document.line_count - 1, len(composer.document.get_line(composer.document.line_count - 1))))
            popup.display = False
            
    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        popup = self.query_one("#command-popup")
        if event.option_list == popup:
            composer = self.query_one("#composer")
            composer.text = str(event.option.prompt)
            composer.move_cursor((composer.document.line_count - 1, len(composer.document.get_line(composer.document.line_count - 1))))
            popup.display = False
            composer.focus()
            
    def on_chat_text_area_submitted(self, event: ChatTextArea.Submitted) -> None:
        if self._turn_worker and self._turn_worker.is_running:
            return

        popup = self.query_one("#command-popup")
        popup.display = False
        
        composer = self.query_one("#composer")
        composer.input_history.add(event.text)
        composer.text = ""
        composer.read_only = True
        
        footer = self.query_one("#footer", Static)
        footer.update("[cyan]Processing...[/cyan]")
        
        self._turn_worker = self.run_turn(event.text)


def launch_tui(
    mode: str = "study",
    topic: str = "general",
    system_prompt: Optional[str] = None,
) -> None:
    from pitagora.chat_controller import ChatController
    controller = ChatController(
        mode=mode,
        topic=topic,
        system_prompt=system_prompt,
    )
    PitagoraApp(controller=controller).run()
