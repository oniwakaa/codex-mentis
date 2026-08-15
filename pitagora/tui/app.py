"""Main Textual Application for Pitagora."""

from pathlib import Path
from typing import Any

from textual.app import App

from pitagora.chat.controller import ChatController
from pitagora.tui.bindings import TUI_BINDINGS
from pitagora.tui.screens import ChatScreen, DashboardScreen, PlotScreen, SettingsScreen

CSS_PATH = Path(__file__).parent / "styles.tcss"


class PitagoraApp(App):
    CSS_PATH = "styles.tcss"
    BINDINGS: list = TUI_BINDINGS
    SCREENS = {
        "chat": ChatScreen,
        "dashboard": DashboardScreen,
        "plot": PlotScreen,
        "settings": SettingsScreen,
    }

    def __init__(self, controller: ChatController | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.controller = controller or ChatController()
        self.reasoning_visible = False
        self.diff_visible = False

    def on_mount(self) -> None:
        self.push_screen("chat")

    def action_cycle_panels(self) -> None:
        screens = ["chat", "plot", "dashboard", "settings"]
        current = self.screen.name if hasattr(self.screen, "name") else "chat"
        idx = (screens.index(current) + 1) % len(screens) if current in screens else 0
        self.switch_screen(screens[idx])

    def action_cancel_op(self) -> None:
        self.notify("Operation cancelled.")

    def action_clear_screen(self) -> None:
        try:
            log_widget = self.screen.query_one("#message-log")
            log_widget.messages = []
        except Exception:
            pass
        self.notify("Screen cleared.")

    def action_toggle_reasoning(self) -> None:
        self.reasoning_visible = not self.reasoning_visible
        state = "visible" if self.reasoning_visible else "hidden"
        self.notify(f"Reasoning trace {state}.")

    def action_open_palette(self) -> None:
        try:
            palette = self.screen.query_one("#command-palette")
            is_visible = palette.styles.display == "block"
            palette.styles.display = "none" if is_visible else "block"
            if not is_visible:
                chat_input = self.screen.query_one("#chat-input")
                if not chat_input.value.startswith("/"):
                    chat_input.value = "/"
                chat_input.focus()
        except Exception:
            pass
        self.notify("Command palette toggled.")


    def action_quit_app(self) -> None:
        self.exit()

    def action_scroll_down(self) -> None:
        if hasattr(self.screen, "scroll_log_down"):
            self.screen.scroll_log_down()

    def action_scroll_up(self) -> None:
        if hasattr(self.screen, "scroll_log_up"):
            self.screen.scroll_log_up()

    def action_page_down(self) -> None:
        if hasattr(self.screen, "page_log_down"):
            self.screen.page_log_down()

    def action_page_up(self) -> None:
        if hasattr(self.screen, "page_log_up"):
            self.screen.page_log_up()

    def action_next_session(self) -> None:
        self.notify("Switched to next session.")

    def action_prev_session(self) -> None:
        self.notify("Switched to previous session.")

    def action_toggle_diff(self) -> None:
        self.diff_visible = not self.diff_visible
        state = "visible" if self.diff_visible else "hidden"
        self.notify(f"Diff view {state}.")

    def action_show_help(self) -> None:
        self.notify("Help overlay: press / for slash commands.")

    def action_close_modal(self) -> None:
        try:
            palette = self.screen.query_one("#command-palette")
            palette.styles.display = "none"
        except Exception:
            pass

