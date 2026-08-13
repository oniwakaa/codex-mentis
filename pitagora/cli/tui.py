from typing import Optional, Dict, Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Static

from pitagora.cli.tui_widgets import (
    ChatTextArea,
    ContextSidebar,
    Conversation,
    QuitScreen,
    SidebarScreen,
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

    #input-area {
        height: 4;
        dock: bottom;
        border-top: solid $primary;
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
        conversation.mount(Static(banner_text, id="banner"))
        conversation.mount(Static("Think. Prove. Understand.", id="tagline"))
        
        # Call list_journeys once. In a real app we'd import it. 
        # But we need to use controller.context["due_reviews"]
        due_reviews = self.controller.context.get("due_reviews")
        if due_reviews:
            self.due_reviews = due_reviews
            conversation.mount(Static(f"Due Reviews: {self.due_reviews}", id="due-reviews-panel"))
            
        self.query_one("#composer").focus()
        self.set_interval(1, self._refresh_elapsed)
        
        sidebar = self.query_one("#sidebar", ContextSidebar)
        sidebar.update_context(self.controller.context)

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

    async def action_request_quit(self) -> None:
        quit_screen = QuitScreen()
        result = await self.push_screen_wait(quit_screen)
        if result:
            self.exit()
            
    def action_clear_visible(self) -> None:
        pass

    def _refresh_elapsed(self) -> None:
        elapsed = self.controller.context.get("elapsed_seconds", 0)
        minutes = elapsed // 60
        seconds = elapsed % 60
        header_context = self.query_one("#header-context", Static)
        header_context.update(f"{minutes:02d}:{seconds:02d}")


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
