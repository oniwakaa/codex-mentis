"""Keybinding definitions for Pitagora Textual TUI."""

from textual.binding import Binding

TUI_BINDINGS = [
    Binding("tab", "cycle_panels", "Cycle Panels", show=True),
    Binding("ctrl+c", "cancel_op", "Cancel", show=True),
    Binding("ctrl+l", "clear_screen", "Clear", show=True),
    Binding("ctrl+r", "toggle_reasoning", "Toggle Trace", show=True),
    Binding("slash", "open_palette", "Command Palette", show=True),
    Binding("q", "quit_app", "Quit", show=True),
    Binding("j", "scroll_down", "Scroll Down", show=False),
    Binding("k", "scroll_up", "Scroll Up", show=False),
    Binding("n", "next_session", "Next Session", show=True),
    Binding("p", "prev_session", "Prev Session", show=True),
    Binding("d", "toggle_diff", "Toggle Diff", show=True),
    Binding("question_mark", "show_help", "Help", show=True),
    Binding("escape", "close_modal", "Close Modal", show=False),
]
