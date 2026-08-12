"""Codex Mentis CLI module."""
# Lazy imports to avoid loading TUI/Textual when not needed
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
    """Launch the REPL (lazy import)."""
    from codex_mentis.cli.repl import launch_repl as _launch
    return _launch(**kwargs)


def get_tui_app():
    """Get the TUI app class (lazy import to avoid Textual dependency at import time)."""
    from codex_mentis.cli.tui import TuiApp
    return TuiApp


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
