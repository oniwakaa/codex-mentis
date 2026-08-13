"""prompt_toolkit-based REPL input — a Claude Code-style input bar.

Typing ``/`` pops up the menu of available slash commands; the bottom toolbar
shows context + hints. Falls back to plain ``input()`` when prompt_toolkit is
unavailable or stdin is not a TTY (so tests / piped input keep working).
"""
from __future__ import annotations

import sys
from typing import Optional

from pitagora.core.constants import CONFIG_DIR

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import NestedCompleter
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.styles import Style
    _HAVE_PTK = True
except Exception:  # pragma: no cover - optional dep
    _HAVE_PTK = False


# Slash-command tree for the autocomplete menu. Leaves are None (no further
# suggestions) or a dict of argument options. Free-text args (e.g. /topic)
# use None so the menu doesn't fire after the command name.
COMMAND_TREE = {
    "/mode": {
        "study": None, "explore": None, "reason": None, "verify": None,
        "tutor": None, "researcher": None, "prover": None, "reviewer": None,
        "visualizer": None, "explainer": None,
        "data": None, "data_analyst": None, "analyze": None,
    },
    "/topic": None,
    "/model": None,
    "/explore": {"--continue": None},
    "/verify": None,
    "/research": None,
    "/save": None,
    "/sessions": None,
    "/resume": None,
    "/quiz": None,
    "/progress": None,
    "/ingest": None,
    "/journeys": None,
    "/dashboard": None,
    "/workflow": {
        "teach": None, "derive_and_prove": None, "concept_mastery": None,
        "debate": None, "deep_research": None, "philosophical_reasoning": None,
    },
    "/latex": None,
    "/rate": {"1": None, "2": None, "3": None, "4": None, "5": None},
    "/help": None,
    "/clear": None,
    "/quit": None,
    "/exit": None,
    "/q": None,
}

_HISTORY_PATH = str(CONFIG_DIR / "repl_history")

_STYLE = Style.from_dict({
    "prompt": "bold ansigreen",
    "bottom-toolbar": "bg:#1a1a2a #888888",
    "bottom-toolbar.key": "bold #6ab0f3",
})

# Single shared session so history + completion state persist across turns.
_session: "Optional[PromptSession]" = None


def _build_session() -> "PromptSession":
    try:
        history = FileHistory(_HISTORY_PATH)
    except Exception:
        history = None
    completer = NestedCompleter.from_nested_dict(COMMAND_TREE)
    return PromptSession(
        history=history,
        completer=completer,
        complete_while_typing=True,
    )


def _toolbar(mode: str, topic: str):
    """Bottom status bar — context + the key hint, Claude Code-style."""
    def _fn():
        return [
            ("class:bottom-toolbar", f" {mode}:{topic}   "),
            ("class:bottom-toolbar.key", "/"),
            ("class:bottom-toolbar", " commands   "),
            ("class:bottom-toolbar.key", "/help"),
            ("class:bottom-toolbar", "   "),
            ("class:bottom-toolbar.key", "/quit"),
            ("class:bottom-toolbar", " to exit"),
        ]
    return _fn


def pitagora_prompt(mode: str, topic: str) -> str:
    """Read one line of user input with slash-command autocomplete.

    Falls back to plain ``input()`` when prompt_toolkit is missing or stdin is
    not a TTY (piped / non-interactive), so the CLI and tests still work.
    """
    if not _HAVE_PTK or not (sys.stdin and sys.stdin.isatty()):
        return input(f"△ pitagora ({mode}:{topic})> ")

    global _session
    if _session is None:
        _session = _build_session()

    prompt_text = [("class:prompt", f"△ pitagora ({mode}:{topic})> ")]
    try:
        return _session.prompt(
            prompt_text,
            style=_STYLE,
            bottom_toolbar=_toolbar(mode, topic),
        )
    except (EOFError, KeyboardInterrupt):
        raise
    except Exception:
        # Any prompt_toolkit failure → degrade to plain input, never crash the REPL.
        return input(f"△ pitagora ({mode}:{topic})> ")
