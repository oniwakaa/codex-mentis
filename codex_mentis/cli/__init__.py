"""Codex Mentis CLI module."""
from codex_mentis.cli.rich_ui import (
    print_markdown,
    print_panel,
    print_math,
    print_plot,
    print_concept_map,
    print_table,
    create_spinner,
    format_proof,
)


def launch_repl(**kwargs):
    """Launch the chat REPL (lazy import)."""
    from codex_mentis.chat import launch_chat
    return launch_chat(**kwargs)


def get_tui_app():
    """TUI removed — use chat.py REPL instead."""
    raise ImportError("TUI removed. Use `codex-mentis` (chat REPL) instead.")


__all__ = [
    "launch_repl",
    "get_tui_app",
    "print_markdown",
    "print_panel",
    "print_math",
    "print_plot",
    "print_concept_map",
    "print_table",
    "create_spinner",
    "format_proof",
]
