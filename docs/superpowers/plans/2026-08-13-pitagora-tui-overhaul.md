# Pitagora TUI overhaul implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a full-screen Textual chat app the default Pitagora experience while preserving the existing Rich REPL as the simple and non-TTY fallback.

**Architecture:** Extract chat state and command handling into a synchronous, UI-neutral `ChatController` that yields `ChatEvent` values. Keep Rich and Textual as thin adapters over that controller. Textual runs controller turns in a thread worker, renders events into a scrollable conversation, and reads sidebar state from the controller.

**Tech Stack:** Python 3.11+, Typer, Rich, Textual 0.38+, prompt-toolkit, pytest, pytest-asyncio.

---

## File map

- Create `pitagora/chat_controller.py`: shared conversation state, slash commands, free-form turns, teaching turns, cached sidebar context, and `ChatEvent`.
- Create `pitagora/cli/tui.py`: `PitagoraApp`, layout, worker lifecycle, event rendering, responsive behavior, and launch function.
- Create `pitagora/cli/tui_widgets.py`: composer, input history, autocomplete, equation segmentation, sidebar, and modal screens.
- Create `tests/test_chat_controller.py`: shared behavior and command parity.
- Create `tests/test_tui.py`: shell, rendering, worker, resize, and keybinding tests.
- Create `tests/test_tui_widgets.py`: pure history/math parsing tests and composer interaction tests.
- Modify `pitagora/chat.py`: retain existing helpers; replace the monolithic loop with the Rich controller adapter.
- Modify `pitagora/cli/app.py`: default TUI selection and `--simple`.
- Modify `pitagora/cli/rich_ui.py`: add Rich renderable builders while preserving print wrappers.
- Modify `pitagora/teaching/ui.py`: add renderable builders and compact teaching variants while preserving show wrappers.
- Modify `pitagora/cli/repl_input.py`: keep `COMMAND_TREE` as the single autocomplete command source.
- Modify `pyproject.toml`: move Textual to the `tui` extra and include it in `all`.
- Modify `README.md`: document TUI installation and simple fallback.
- Modify `tests/test_cli_app.py`: launcher selection and `--simple` coverage.

## Task 1: Prepare the test environment and record baseline

**Files:**
- Read: `pyproject.toml`
- Read: `.gitignore`

- [ ] **Step 1: Create an ignored project virtual environment**

Run:

```bash
cd /Users/carlo/Desktop/pr_prj/pitagora
python3 -m venv .venv
```

Expected: `.venv/bin/python` exists and `.venv/` remains ignored by Git.

- [ ] **Step 2: Install the project with development and TUI extras**

Run:

```bash
cd /Users/carlo/Desktop/pr_prj/pitagora
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

Expected: installation succeeds; importing `matplotlib`, `pytest`, and
`textual.widgets.TextArea` succeeds.

- [ ] **Step 3: Run the required pre-change baseline**

Run:

```bash
cd /Users/carlo/Desktop/pr_prj/pitagora
.venv/bin/python -m pytest tests/ -q
```

Expected: all collected tests pass. The system interpreter baseline was blocked
before collection by `ModuleNotFoundError: No module named 'matplotlib'`; use
the virtual environment for every later check.

## Task 2: Add CLI selection and optional dependency wiring

**Files:**
- Modify: `pitagora/cli/app.py:220-279`
- Modify: `pyproject.toml:17-56`
- Modify: `tests/test_cli_app.py`

- [ ] **Step 1: Write failing launcher-selection tests**

Append tests that isolate selection from the first-run setup wizard:

```python
from unittest.mock import Mock

import pitagora.cli.app as cli_app


def test_select_chat_launcher_uses_simple_when_requested(monkeypatch):
    simple = Mock()
    monkeypatch.setattr(cli_app, "_load_simple_launcher", lambda: simple)
    monkeypatch.setattr(cli_app, "_load_tui_launcher", Mock())
    monkeypatch.setattr(cli_app, "_is_interactive", lambda: True)

    assert cli_app._select_chat_launcher(simple=True) is simple


def test_select_chat_launcher_uses_simple_for_non_tty(monkeypatch):
    simple = Mock()
    monkeypatch.setattr(cli_app, "_load_simple_launcher", lambda: simple)
    monkeypatch.setattr(cli_app, "_load_tui_launcher", Mock())
    monkeypatch.setattr(cli_app, "_is_interactive", lambda: False)

    assert cli_app._select_chat_launcher(simple=False) is simple


def test_select_chat_launcher_uses_tui_by_default(monkeypatch):
    tui = Mock()
    monkeypatch.setattr(cli_app, "_load_simple_launcher", Mock())
    monkeypatch.setattr(cli_app, "_load_tui_launcher", lambda: tui)
    monkeypatch.setattr(cli_app, "_is_interactive", lambda: True)

    assert cli_app._select_chat_launcher(simple=False) is tui


def test_select_chat_launcher_falls_back_when_textual_missing(monkeypatch, capsys):
    simple = Mock()

    def missing_textual():
        raise ModuleNotFoundError("No module named 'textual'", name="textual")

    monkeypatch.setattr(cli_app, "_load_simple_launcher", lambda: simple)
    monkeypatch.setattr(cli_app, "_load_tui_launcher", missing_textual)
    monkeypatch.setattr(cli_app, "_is_interactive", lambda: True)

    assert cli_app._select_chat_launcher(simple=False) is simple
    assert "pip install pitagora[tui]" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests and verify the missing helper failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli_app.py -q
```

Expected: the four new tests fail because `_select_chat_launcher` and loader
helpers do not exist.

- [ ] **Step 3: Implement lazy launcher selection**

Add to `pitagora/cli/app.py` above the `chat` command:

```python
def _is_interactive() -> bool:
    import sys

    return bool(
        sys.stdin
        and sys.stdout
        and sys.stdin.isatty()
        and sys.stdout.isatty()
    )


def _load_simple_launcher():
    from pitagora.chat import launch_chat

    return launch_chat


def _load_tui_launcher():
    from pitagora.cli.tui import launch_tui

    return launch_tui


def _select_chat_launcher(simple: bool):
    fallback = _load_simple_launcher()
    if simple or not _is_interactive():
        return fallback
    try:
        return _load_tui_launcher()
    except ModuleNotFoundError as exc:
        if exc.name != "textual" and not str(exc.name).startswith("textual."):
            raise
        typer.echo(
            "Textual is not installed; run `pip install pitagora[tui]`. "
            "Falling back to simple mode."
        )
        return fallback
```

Add `simple` to both Typer entry points and call the selected launcher:

```python
simple: bool = typer.Option(
    False,
    "--simple",
    help="Use the Rich line-oriented chat instead of the full-screen TUI",
)
```

For `chat_cmd`, call:

```python
launcher = _select_chat_launcher(simple)
launcher(mode=mode, topic=topic)
```

For `main_callback`, preserve the first-run wizard and model environment setup,
then call:

```python
launcher = _select_chat_launcher(simple)
launcher()
```

- [ ] **Step 4: Move Textual to the optional extra**

Remove `"textual>=0.30.0"` from `[project].dependencies`. Add:

```toml
tui = [
    "textual>=0.38.0",
]
```

Add `"textual>=0.38.0"` to `all`.

- [ ] **Step 5: Run CLI tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli_app.py tests/test_cli_commands.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit CLI selection**

```bash
git add pyproject.toml pitagora/cli/app.py tests/test_cli_app.py
git commit -F - <<'EOF'
feat(cli): select Textual chat by default

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
EOF
```

## Task 3: Introduce controller events and free-form turns

**Files:**
- Create: `pitagora/chat_controller.py`
- Create: `tests/test_chat_controller.py`
- Read: `pitagora/chat.py:1-404`

- [ ] **Step 1: Write failing free-form controller tests**

Create `tests/test_chat_controller.py`:

```python
from pitagora.chat_controller import ChatController, ChatEvent


def make_controller(completion=lambda messages, model=None, config=None: "answer"):
    return ChatController(
        mode="study",
        topic="limits",
        config={"default_model": "test-model"},
        completion=completion,
        rag_lookup=lambda query: "[rag]",
        concept_lookup=lambda topic: "[concept]",
        verify_math=lambda response: None,
        save_memory=lambda role, content, topic: None,
        record_study=lambda topic, user_input: None,
        due_reviews=lambda: None,
        user_context="",
        feedback_loop=(None, None, None),
    )


def test_freeform_turn_emits_user_status_and_markdown():
    controller = make_controller()

    events = list(controller.handle_input("What is a limit?"))

    assert [event.kind for event in events] == [
        "user",
        "status",
        "markdown",
        "state_changed",
    ]
    assert events[0].content == "What is a limit?"
    assert events[2].content == "answer"
    assert controller.messages[-2]["content"].endswith(
        "User question: What is a limit?"
    )
    assert controller.messages[-1] == {"role": "assistant", "content": "answer"}


def test_empty_input_emits_nothing():
    assert list(make_controller().handle_input("   ")) == []


def test_context_reports_session_state():
    controller = make_controller()
    list(controller.handle_input("hello"))

    context = controller.context

    assert context["mode"] == "study"
    assert context["topic"] == "limits"
    assert context["model"] == "test-model"
    assert context["message_count"] == 1
    assert context["teaching"] is False
```

- [ ] **Step 2: Run tests and verify import failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_chat_controller.py -q
```

Expected: collection fails because `pitagora.chat_controller` does not exist.

- [ ] **Step 3: Implement the event and controller base**

Create `pitagora/chat_controller.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterator, Optional

from pitagora import chat as chat_runtime


@dataclass(frozen=True)
class ChatEvent:
    kind: str
    content: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChatController:
    def __init__(
        self,
        mode: str = "study",
        topic: str = "general",
        system_prompt: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
        completion: Optional[Callable[..., str]] = None,
        rag_lookup: Optional[Callable[[str], str]] = None,
        concept_lookup: Optional[Callable[[str], str]] = None,
        verify_math: Optional[Callable[[str], Optional[str]]] = None,
        save_memory: Optional[Callable[..., None]] = None,
        record_study: Optional[Callable[..., None]] = None,
        due_reviews: Optional[Callable[[], Optional[str]]] = None,
        user_context: Optional[str] = None,
        feedback_loop: Optional[tuple[Any, Any, Any]] = None,
    ) -> None:
        self.mode = mode
        self.topic = topic
        self.config = config or chat_runtime.load_provider_config()
        self.model = self.config.get("default_model", "unknown")
        self.completion = completion or chat_runtime.chat_completion
        self.rag_lookup = rag_lookup or chat_runtime._get_rag_context
        self.concept_lookup = concept_lookup or chat_runtime._get_concept_context
        self.verify_math = verify_math or chat_runtime._verify_math
        self.save_memory = save_memory or chat_runtime._save_to_memory
        self.record_study = record_study or chat_runtime._record_study
        self.due_reviews = due_reviews or chat_runtime._check_due_reviews
        self.started_at = datetime.now()
        self.message_count = 0
        self.teaching_session = None
        self.teaching_analyzer = None
        self.teaching_journey = None
        self.last_freeform = {"topic": topic, "strategy": "socratic"}
        self.system_prompt = system_prompt or self._default_system_prompt()
        context_text = (
            chat_runtime._get_user_context()
            if user_context is None
            else user_context
        )
        if context_text:
            self.system_prompt += f"\n\n{context_text}"
        self.messages = [{"role": "system", "content": self.system_prompt}]
        loop = (
            chat_runtime._build_feedback_loop()
            if feedback_loop is None
            else feedback_loop
        )
        (
            self.feedback_improver,
            self.feedback_skill_evo,
            self.feedback_skills_engine,
        ) = loop
        self._due_review_message = self.due_reviews()

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are Pitagora, an expert mathematics and physics tutor. "
            "You explain concepts clearly using the Socratic method: ask guiding "
            "questions before giving answers. Use LaTeX notation for equations "
            "($..$ inline, $$...$$ display). Be precise, rigorous, and encouraging. "
            "When a student makes a mistake, guide them to discover the error rather "
            "than just correcting it. Use markdown formatting for structure."
        )

    @property
    def context(self) -> dict[str, Any]:
        session = self.teaching_session
        return {
            "mode": self.mode,
            "topic": self.topic,
            "model": self.model,
            "message_count": self.message_count,
            "elapsed_seconds": int((datetime.now() - self.started_at).total_seconds()),
            "teaching": session is not None,
            "comprehension": session.comprehension_score if session else 0.0,
            "sub_concepts": (
                [item.to_dict() for item in session.sub_concepts] if session else []
            ),
            "journey": getattr(self.teaching_journey, "topic", None),
            "journey_progress": (
                (session.current_index + 1) / len(session.sub_concepts)
                if session and session.sub_concepts
                else 0.0
            ),
            "due_reviews": self._due_review_message,
        }

    def handle_input(self, user_input: str) -> Iterator[ChatEvent]:
        text = user_input.strip()
        if not text:
            return
        if text.startswith("/"):
            yield from self._handle_command(text)
            return
        if self.teaching_session is not None:
            yield from self._handle_teaching_turn(text)
            return
        yield from self._handle_freeform_turn(user_input)

    def _handle_freeform_turn(self, user_input: str) -> Iterator[ChatEvent]:
        yield ChatEvent("user", user_input)
        rag_context = self.rag_lookup(user_input)
        concept_context = self.concept_lookup(self.topic)
        contexts = [value for value in (rag_context, concept_context) if value]
        enriched = (
            "\n\n".join(contexts) + f"\n\nUser question: {user_input}"
            if contexts
            else user_input
        )
        self.messages.append({"role": "user", "content": enriched})
        yield ChatEvent("status", "Thinking...", {"busy": True})
        response = self.completion(
            self.messages,
            model=self.model,
            config=self.config,
        )
        self.messages.append({"role": "assistant", "content": response})
        yield ChatEvent("markdown", response)
        verification = self.verify_math(response)
        if verification:
            yield ChatEvent("status", verification, {"verification": True})
        self.save_memory("user", user_input, topic=self.topic)
        self.save_memory("assistant", response, topic=self.topic)
        self.record_study(self.topic, user_input)
        self.message_count += 1
        self.last_freeform = {"topic": self.topic, "strategy": "socratic"}
        yield ChatEvent("state_changed", metadata={"context": self.context})
```

Add temporary command and teaching methods that emit a clear unsupported error
until Tasks 4 and 5 replace them:

```python
    def _handle_command(self, text: str) -> Iterator[ChatEvent]:
        yield ChatEvent("error", f"Command unavailable: {text.split()[0]}")

    def _handle_teaching_turn(self, text: str) -> Iterator[ChatEvent]:
        yield ChatEvent("error", "Teaching mode is not initialized.")
```

- [ ] **Step 4: Run controller tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_chat_controller.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit controller base**

```bash
git add pitagora/chat_controller.py tests/test_chat_controller.py
git commit -F - <<'EOF'
feat(chat): add shared conversation controller

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
EOF
```

## Task 4: Extract all non-teaching slash commands

**Files:**
- Modify: `pitagora/chat_controller.py`
- Modify: `tests/test_chat_controller.py`
- Read: `pitagora/chat.py:533-954`
- Read: `pitagora/cli/repl_input.py:28-71`

- [ ] **Step 1: Write failing command parity and state tests**

Append:

```python
from pitagora.cli.repl_input import COMMAND_TREE


def test_controller_has_handler_for_every_repl_command():
    assert set(COMMAND_TREE).issubset(ChatController.COMMANDS)


def test_mode_topic_and_model_commands_update_context():
    controller = make_controller()

    list(controller.handle_input("/mode reason"))
    list(controller.handle_input("/topic derivatives"))
    list(controller.handle_input("/model another-model"))

    assert controller.context["mode"] == "reason"
    assert controller.context["topic"] == "derivatives"
    assert controller.context["model"] == "another-model"


def test_clear_resets_messages_but_keeps_system_prompt():
    controller = make_controller()
    list(controller.handle_input("hello"))

    events = list(controller.handle_input("/clear"))

    assert controller.messages == [
        {"role": "system", "content": controller.system_prompt}
    ]
    assert events[-1].kind == "state_changed"


def test_quit_emits_quit_request():
    events = list(make_controller().handle_input("/quit"))

    assert events[-1].metadata["quit"] is True


def test_unknown_command_is_visible():
    events = list(make_controller().handle_input("/not-real"))

    assert events == [ChatEvent("error", "Unknown: /not-real. /help for commands.")]
```

- [ ] **Step 2: Run tests and verify missing command mapping**

Run:

```bash
.venv/bin/python -m pytest tests/test_chat_controller.py -q
```

Expected: new tests fail because `COMMANDS` and real command handlers are absent.

- [ ] **Step 3: Add exact command dispatch**

Define this complete mapping on `ChatController`:

```python
    COMMANDS = {
        "/mode": "_cmd_mode",
        "/topic": "_cmd_topic",
        "/model": "_cmd_model",
        "/explore": "_cmd_explore",
        "/verify": "_cmd_verify",
        "/research": "_cmd_research",
        "/save": "_cmd_save",
        "/sessions": "_cmd_sessions",
        "/resume": "_cmd_resume",
        "/quiz": "_cmd_quiz",
        "/progress": "_cmd_progress",
        "/ingest": "_cmd_ingest",
        "/journeys": "_cmd_journeys",
        "/dashboard": "_cmd_dashboard",
        "/workflow": "_cmd_workflow",
        "/latex": "_cmd_latex",
        "/rate": "_cmd_rate",
        "/help": "_cmd_help",
        "/clear": "_cmd_clear",
        "/quit": "_cmd_quit",
        "/exit": "_cmd_quit",
        "/q": "_cmd_quit",
    }
```

Replace `_handle_command` with:

```python
    def _handle_command(self, text: str) -> Iterator[ChatEvent]:
        command, _, argument = text.partition(" ")
        command = command.lower()
        handler_name = self.COMMANDS.get(command)
        if handler_name is None:
            yield ChatEvent("error", f"Unknown: {command}. /help for commands.")
            return
        yield from getattr(self, handler_name)(argument.strip())
```

Implement `_cmd_mode`, `_cmd_topic`, `_cmd_model`, `_cmd_clear`, and `_cmd_quit`
as direct state changes. Move `/save`, `/sessions`, `/resume`, `/latex`,
`/rate`, and `/help` from the matching `chat.py` branches without changing
their messages or persistence calls. Each console print becomes a `status`,
`error`, `markdown`, or `renderable` event. Every mutation ends with:

```python
yield ChatEvent("state_changed", metadata={"context": self.context})
```

Use `Panel` for help and `render_equation_box()` output as `renderable` content.
`/resume` assigns loaded messages only when loading succeeds. `/rate` keeps the
current 1-5 validation and feedback-loop call.

- [ ] **Step 4: Extract service-backed commands**

Move the existing behavior for `/verify`, `/research`, `/quiz`, `/progress`,
`/ingest`, `/journeys`, `/dashboard`, and `/workflow` into the mapped methods.
Keep current limits, including ten ingested files and five shown research
findings. Emit `status` before long work and a terminal event after it.

Keep command-specific imports inside each method. This preserves lazy loading
and avoids making unrelated CLI commands depend on optional integrations.

- [ ] **Step 5: Run command tests and existing subsystem tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_chat_controller.py \
  tests/test_session_persistence.py \
  tests/test_journeys.py \
  tests/test_math_sandbox.py \
  tests/test_cli_commands.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit command extraction**

```bash
git add pitagora/chat_controller.py tests/test_chat_controller.py
git commit -F - <<'EOF'
refactor(chat): centralize slash commands

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
EOF
```

## Task 5: Extract teaching mode and journey persistence

**Files:**
- Modify: `pitagora/chat_controller.py`
- Modify: `tests/test_chat_controller.py`
- Read: `pitagora/chat.py:405-496`
- Read: `pitagora/chat.py:720-789`
- Read: `pitagora/chat.py:949-1010`

- [ ] **Step 1: Write failing teaching tests**

Append tests using monkeypatches so no real provider or user data is touched:

```python
from pitagora.teaching.analyzer import ResponseClassification
from pitagora.teaching.session import TeachingState
from pitagora.journeys.model import LearningJourney


class CorrectAnalyzer:
    def classify(self, text, topic, sub_concept, config=None, model=None):
        return ResponseClassification(
            label="correct",
            delta=0.15,
            rationale="test",
            via_shortcut=text == "n",
        )


def test_explore_starts_teaching_and_emits_inline_widgets(monkeypatch):
    controller = make_controller()
    monkeypatch.setattr(
        "pitagora.chat_controller.chat_runtime._generate_sub_concepts",
        lambda topic, config, model: ["Definition", "Examples"],
    )
    monkeypatch.setattr(
        "pitagora.chat_controller.ResponseAnalyzer",
        lambda completion: CorrectAnalyzer(),
    )

    events = list(controller.handle_input("/explore limits"))

    assert controller.teaching_session.topic == "limits"
    assert controller.teaching_session.state in {
        TeachingState.exploring,
        TeachingState.checking,
    }
    assert {"markdown", "comprehension", "subconcepts", "controls"}.issubset(
        {event.kind for event in events}
    )


def test_pause_shortcut_saves_and_leaves_teaching(monkeypatch):
    controller = make_controller()
    controller.teaching_session = __import__(
        "pitagora.teaching.session", fromlist=["TeachingSession"]
    ).TeachingSession("limits", ["Definition"])
    controller.teaching_session.transition(TeachingState.exploring)
    controller.teaching_journey = LearningJourney(
        topic="limits",
        sub_concepts=[
            {"name": "Definition", "mastery": 0.0, "visited": False}
        ],
    )
    saved = []
    monkeypatch.setattr(
        "pitagora.journeys.store.save_journey",
        lambda journey: saved.append(journey),
    )

    events = list(controller.handle_input("p"))

    assert controller.teaching_session is None
    assert events[-1].kind == "state_changed"
```

- [ ] **Step 2: Run tests and verify teaching failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_chat_controller.py -q
```

Expected: new teaching tests fail because `/explore` and teaching event kinds
are not implemented.

- [ ] **Step 3: Implement `/explore` and resume**

Import `ResponseAnalyzer`, `TeachingSession`, and `TeachingState` in
`chat_controller.py`. Move the existing `/explore <topic>` and
`/explore --continue` branches into `_cmd_explore`.

For a new session:

1. emit `status("Designing learning path...")`;
2. call `_generate_sub_concepts`;
3. create and seed `TeachingSession`;
4. create or resume the learning journey;
5. emit a topic overview `renderable`;
6. call `_run_teaching_turn_events("begin")`; and
7. emit `state_changed`.

For `--continue`, load the newest active or paused journey, rebuild
`TeachingSession`, set `topic`, and emit comprehension, controls, and state.

- [ ] **Step 4: Implement event-based teaching turns**

Move the state changes and persistence from `_run_teaching_turn()` into:

```python
    def _run_teaching_turn_events(self, user_input: str) -> Iterator[ChatEvent]:
```

Keep classification, feedback recording, style selection, action policy,
prompt construction, state transitions, and journey updates unchanged. Replace
console operations with:

```python
yield ChatEvent("status", "Teaching...")
yield ChatEvent("markdown", response)
yield ChatEvent(
    "comprehension",
    self.teaching_session.comprehension_score,
)
yield ChatEvent(
    "subconcepts",
    [item.to_dict() for item in self.teaching_session.sub_concepts],
    {"current_index": self.teaching_session.current_index},
)
yield ChatEvent("controls")
yield ChatEvent("state_changed", metadata={"context": self.context})
```

`_handle_teaching_turn()` handles `p` first, saves the journey, clears teaching
state, and emits the existing pause message. Other replies delegate to the
event method. Completion emits the existing session summary as a `renderable`
and clears teaching state.

- [ ] **Step 5: Run teaching and controller tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_chat_controller.py \
  tests/test_teaching_session.py \
  tests/test_teaching_analyzer.py \
  tests/test_journeys.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit teaching extraction**

```bash
git add pitagora/chat_controller.py tests/test_chat_controller.py
git commit -F - <<'EOF'
refactor(teaching): route sessions through controller

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
EOF
```

## Task 6: Replace the old loop with a Rich adapter

**Files:**
- Modify: `pitagora/chat.py:405-1062`
- Modify: `tests/test_chat_controller.py`

- [ ] **Step 1: Write a failing Rich adapter test**

Append:

```python
from rich.console import Console

from pitagora.chat import launch_chat


class FakeController:
    mode = "study"
    topic = "general"
    model = "test-model"

    def startup_events(self):
        return [ChatEvent("status", "welcome")]

    def handle_input(self, text):
        if text == "/quit":
            return iter(
                [
                    ChatEvent("status", "Goodbye! Keep reasoning."),
                    ChatEvent("state_changed", metadata={"quit": True}),
                ]
            )
        return iter([ChatEvent("markdown", "answer")])


def test_launch_chat_renders_controller_events():
    inputs = iter(["hello", "/quit"])
    console = Console(record=True, width=80)

    launch_chat(
        controller=FakeController(),
        input_reader=lambda mode, topic: next(inputs),
        con=console,
    )

    output = console.export_text()
    assert "answer" in output
    assert "Goodbye! Keep reasoning." in output
```

- [ ] **Step 2: Run the adapter test and verify signature failure**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_chat_controller.py::test_launch_chat_renders_controller_events -q
```

Expected: failure because `launch_chat()` does not accept adapter dependencies.

- [ ] **Step 3: Implement Rich event rendering**

Add:

```python
def _render_rich_event(console, event) -> bool:
    from rich.markdown import Markdown

    if event.kind == "markdown":
        console.print(Markdown(str(event.content)))
    elif event.kind == "renderable":
        console.print(event.content)
    elif event.kind == "error":
        console.print(f"[red]{event.content}[/red]")
    elif event.kind == "comprehension":
        from pitagora.teaching.ui import show_comprehension_gauge
        show_comprehension_gauge(float(event.content), console)
    elif event.kind == "subconcepts":
        from pitagora.teaching.ui import show_subconcept_progress
        show_subconcept_progress(
            event.content,
            event.metadata["current_index"],
            console,
        )
    elif event.kind == "controls":
        from pitagora.teaching.ui import show_controls
        show_controls(console)
    elif event.kind == "status" and not event.metadata.get("busy"):
        console.print(f"[dim]{event.content}[/dim]")
    return bool(event.metadata.get("quit"))
```

Replace `launch_chat()` with an adapter that accepts optional `controller`,
`input_reader`, and `con`, constructs defaults lazily, shows the existing
welcome banner, checks due reviews, and iterates `controller.handle_input()`.
For a busy `status` event, start `console.status`; stop it before rendering the
next event. Break when `_render_rich_event()` returns true.

Do not change public `mode`, `topic`, or `system_prompt` arguments.

- [ ] **Step 4: Remove duplicated loop logic**

Delete command and turn branches now owned by `ChatController`. Keep helper
functions used by the controller, including `_generate_sub_concepts`,
`_build_teaching_prompt`, `_seed_session_style`, and feedback/RAG/memory/math
helpers.

- [ ] **Step 5: Run fallback and legacy tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_chat_controller.py \
  test_legacy.py \
  test_new_features_legacy.py \
  test_system_legacy.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit the Rich adapter**

```bash
git add pitagora/chat.py tests/test_chat_controller.py
git commit -F - <<'EOF'
refactor(chat): make Rich REPL a controller adapter

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
EOF
```

## Task 7: Make existing Rich widgets reusable

**Files:**
- Modify: `pitagora/cli/rich_ui.py`
- Modify: `pitagora/teaching/ui.py`
- Create: `tests/test_tui_widgets.py`

- [ ] **Step 1: Write failing renderable-builder tests**

Create `tests/test_tui_widgets.py`:

```python
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from pitagora.cli.rich_ui import build_equation_block, build_plot, build_table
from pitagora.teaching.ui import (
    build_comprehension_gauge,
    build_controls,
    build_subconcept_progress,
)


def render(renderable):
    console = Console(record=True, width=80)
    console.print(renderable)
    return console.export_text()


def test_equation_builder_returns_panel():
    result = build_equation_block(
        [{"equation": r"x^2", "annotation": "square"}],
        title="Math",
    )
    assert isinstance(result, Panel)
    assert "(1)" in render(result)


def test_table_builder_expands_and_stripes_rows():
    result = build_table(["A"], [["one"], ["two"]], title="Data")
    assert result.expand is True
    assert result.row_styles == ["none", "dim"]


def test_plot_builder_returns_titled_panel():
    result = build_plot([0, 1], [0, 1], "Line", "x", "y")
    assert isinstance(result, Panel)
    assert result.title == "Line"


def test_compact_teaching_builders_return_renderables():
    gauge = build_comprehension_gauge(0.75)
    progress = build_subconcept_progress(
        [{"name": "Definition", "mastery": 0.8, "visited": True}],
        0,
        compact=True,
    )
    controls = build_controls()
    assert isinstance(gauge, Text)
    assert isinstance(progress, Text)
    assert isinstance(controls, Text)
```

- [ ] **Step 2: Run tests and verify missing builders**

Run:

```bash
.venv/bin/python -m pytest tests/test_tui_widgets.py -q
```

Expected: collection fails because builder functions do not exist.

- [ ] **Step 3: Add builders without changing print APIs**

For each affected function, move renderable construction into a `build_*`
function and keep the existing wrapper:

```python
def build_comprehension_gauge(score: float) -> Text:
    color = _score_color(score)
    width = 20
    filled = int(round(score * width))
    return Text.assemble(
        ("█" * filled + "░" * (width - filled), color),
        f" {score * 100:5.1f}% comprehension",
    )


def show_comprehension_gauge(
    score: float,
    con: Optional[Console] = None,
) -> None:
    (con or console).print(build_comprehension_gauge(score))
```

`build_subconcept_progress(..., compact=True)` returns one `Text` line with the
current marker and semicolon-separated concepts. The default returns the
existing `Panel`. `build_controls()` returns `Text.from_markup(CONTROLS_LINE)`.

In `rich_ui.py`, add builders for table, equation block, concept map, mastery
dashboard, split reasoning, and plots. `build_plot()` uses Plotext's
`build()` output and wraps `Text.from_ansi()` in a titled `Panel`; `print_plot`
prints that panel instead of calling `plotext.show()`. Set table `expand=True` and
`row_styles=["none", "dim"]`. Existing `print_*` functions print their builder
result and keep their signatures.

- [ ] **Step 4: Run UI helper tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_tui_widgets.py tests/test_math_plots.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit reusable renderables**

```bash
git add pitagora/cli/rich_ui.py pitagora/teaching/ui.py tests/test_tui_widgets.py
git commit -F - <<'EOF'
refactor(ui): expose reusable Rich renderables

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
EOF
```

## Task 8: Build the Textual shell, startup, and responsive sidebar

**Files:**
- Create: `pitagora/cli/tui.py`
- Create: `pitagora/cli/tui_widgets.py`
- Create: `tests/test_tui.py`
- Modify: `tests/test_tui_widgets.py`

- [ ] **Step 1: Write failing shell and resize tests**

Create `tests/test_tui.py`:

```python
import pytest

from pitagora.chat_controller import ChatEvent
from pitagora.cli.tui import PitagoraApp


class FakeController:
    context = {
        "mode": "study",
        "topic": "limits",
        "model": "test-model",
        "message_count": 0,
        "elapsed_seconds": 0,
        "teaching": False,
        "comprehension": 0.0,
        "sub_concepts": [],
        "journey": None,
        "due_reviews": None,
    }

    def __init__(self):
        self.received = []

    def handle_input(self, text):
        self.received.append(text)
        return iter([ChatEvent("markdown", "answer")])


@pytest.mark.asyncio
async def test_shell_mounts_and_focuses_composer():
    app = PitagoraApp(controller=FakeController())
    async with app.run_test(size=(120, 40)):
        assert app.query_one("#brand").renderable.plain.startswith("△ PITAGORA")
        assert app.query_one("#composer").has_focus
        assert app.query_one("#sidebar").display is True
        assert "Think. Prove. Understand." in app.query_one(
            "#conversation"
        ).renderable_text


@pytest.mark.asyncio
async def test_sidebar_hides_below_100_columns():
    app = PitagoraApp(controller=FakeController())
    async with app.run_test(size=(80, 30)):
        assert app.query_one("#sidebar").display is False


@pytest.mark.asyncio
async def test_compact_mode_hides_sidebar():
    app = PitagoraApp(controller=FakeController())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+x")
        assert app.has_class("compact")
        assert app.query_one("#sidebar").display is False
```

- [ ] **Step 2: Run tests and verify missing module**

Run:

```bash
.venv/bin/python -m pytest tests/test_tui.py -q
```

Expected: collection fails because `pitagora.cli.tui` does not exist.

- [ ] **Step 3: Add shell widgets and CSS**

In `tui_widgets.py`, add:

- `ContextSidebar(Static)` with `update_context(context)`;
- `SidebarScreen(ModalScreen)` for narrow overlay;
- `QuitScreen(ModalScreen[bool])` with Quit and Cancel buttons; and
- a `Conversation(VerticalScroll)` that exposes `renderable_text` for tests.

Render sidebar context with `Table.grid(expand=True)`, `ProgressBar`, and
colored sub-concept dots. Use only cached values from `controller.context`.

In `tui.py`, compose:

```python
class PitagoraApp(App):
    BINDINGS = [
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=False),
        Binding("ctrl+l", "clear_visible", "Clear", show=False),
        Binding("ctrl+x", "toggle_compact", "Compact", show=False),
        Binding("escape", "request_quit", "Quit", show=False),
        Binding("ctrl+c", "request_quit", "Quit", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static(Text("△ PITAGORA", style="bold #ffd700"), id="brand"),
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
```

Use an inline `CSS` string with deep-indigo header/footer, gold brand, cyan
interactive accents, flexible `#main`, 28-column sidebar, four-line input area,
message spacing, and `.compact` overrides.

- [ ] **Step 4: Add startup content and responsive behavior**

Mount a gold six-line triangle/PITAGORA banner, tagline, and welcome panel into
`#conversation` during `on_mount`. Before rendering the panel, call
`list_journeys()` once and derive active journey names and progress from its
cached summaries; use `controller.context["due_reviews"]` for review text. Set
composer focus afterward. Cache both values on the app and refresh them only
after `state_changed` events from journey commands.

In `on_resize`, call `_apply_sidebar_layout(event.size.width)`. Width below 100
hides inline sidebar. `action_toggle_sidebar()` toggles inline display when
wide and pushes `SidebarScreen(self.controller.context)` when narrow.

`action_toggle_compact()` toggles the app `compact` class and reapplies sidebar
layout. `set_interval(1, self._refresh_elapsed)` updates elapsed time without
reloading journey or review data.

- [ ] **Step 5: Add `launch_tui`**

```python
def launch_tui(
    mode: str = "study",
    topic: str = "general",
    system_prompt: Optional[str] = None,
) -> None:
    controller = ChatController(
        mode=mode,
        topic=topic,
        system_prompt=system_prompt,
    )
    PitagoraApp(controller=controller).run()
```

- [ ] **Step 6: Run shell tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_tui.py tests/test_tui_widgets.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit the shell**

```bash
git add pitagora/cli/tui.py pitagora/cli/tui_widgets.py tests/test_tui.py tests/test_tui_widgets.py
git commit -F - <<'EOF'
feat(tui): add full-screen Pitagora shell

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
EOF
```

## Task 9: Implement composer history, multiline input, and autocomplete

**Files:**
- Modify: `pitagora/cli/tui_widgets.py`
- Modify: `pitagora/cli/tui.py`
- Modify: `tests/test_tui_widgets.py`
- Modify: `tests/test_tui.py`

- [ ] **Step 1: Write failing pure history and math segmentation tests**

Append to `tests/test_tui_widgets.py`:

```python
from pitagora.cli.tui_widgets import InputHistory, split_math


def test_history_caps_at_100_and_navigates():
    history = InputHistory(limit=100)
    for index in range(105):
        history.add(f"message {index}")

    assert len(history.items) == 100
    assert history.previous() == "message 104"
    assert history.previous() == "message 103"
    assert history.next() == "message 104"
    assert history.next() == ""


def test_split_math_keeps_markdown_and_numbers_display_equations():
    parts = split_math("Before $x^2$.\n\n$$x^2 + y^2 = z^2$$\n\nAfter.")

    assert parts == [
        ("markdown", "Before x².\n\n"),
        ("equation", "x² + y² = z²", 1),
        ("markdown", "\n\nAfter."),
    ]
```

- [ ] **Step 2: Write failing composer interaction tests**

Append to `tests/test_tui.py`:

```python
@pytest.mark.asyncio
async def test_enter_sends_and_shift_enter_inserts_newline():
    app = PitagoraApp(controller=FakeController())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("h", "i", "shift+enter", "t", "h", "e", "r", "e")
        assert app.query_one("#composer").text == "hi\nthere"
        await pilot.press("enter")
        await pilot.pause()
        assert app.query_one("#composer").text == ""
        assert "answer" in app.query_one("#conversation").renderable_text


@pytest.mark.asyncio
async def test_multiline_paste_submits_as_one_message():
    controller = FakeController()
    app = PitagoraApp(controller=controller)
    async with app.run_test(size=(120, 40)) as pilot:
        composer = app.query_one("#composer")
        composer.insert("first line\nsecond line")
        await pilot.press("enter")
        await pilot.pause()
        assert controller.received == ["first line\nsecond line"]


@pytest.mark.asyncio
async def test_slash_opens_autocomplete_and_tab_completes():
    app = PitagoraApp(controller=FakeController())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("/")
        assert app.query_one("#command-popup").display is True
        await pilot.press("h", "e", "tab")
        assert app.query_one("#composer").text == "/help"
```

- [ ] **Step 3: Run tests and verify missing behavior**

Run:

```bash
.venv/bin/python -m pytest tests/test_tui_widgets.py tests/test_tui.py -q
```

Expected: new tests fail because history, math segmentation, and composer
bindings are absent.

- [ ] **Step 4: Implement `InputHistory` and `split_math`**

`InputHistory.add()` ignores blank entries and consecutive duplicates, keeps
the newest 100, and resets its cursor. `previous()` and `next()` return the
current draft boundary as an empty string.

`split_math()` uses the existing `latex_to_unicode()` helper. Split
non-overlapping `$$...$$` blocks with `re.DOTALL`, convert `$...$` inside
Markdown segments, and return tuples of kind, content, and equation number.

- [ ] **Step 5: Implement `ChatTextArea`**

Subclass `TextArea` and define `Submitted`, `AutocompleteRequested`, and
`AutocompleteNavigate` messages. Override `_on_key`:

```python
def _on_key(self, event: events.Key) -> None:
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
    if event.key in {"up", "down"}:
        self.post_message(self.AutocompleteNavigate(self, event.key))
    super()._on_key(event)
```

Before passing Up or Down to `super()`, use history only at the first or last
document row and only when autocomplete is hidden. Load the selected entry and
move `cursor_location` to `document.end`.

When teaching mode is active and composer text is empty, intercept
`n/e/d/s/?/v/q/p`, post `Submitted`, and prevent insertion.

Give test fakes a `received` list and append every input in `handle_input`, so
the paste test verifies one controller call rather than only widget contents.

- [ ] **Step 6: Implement command popup**

Add `CommandPopup(OptionList)` populated from `COMMAND_TREE`. Filter commands
from `TextArea.Changed`; show only when text starts with `/` and has no space.
Up and Down move the highlighted option. Tab inserts the highlighted command
and hides the popup. Clicking an option does the same.

On submission, add the full multiline value to history, clear the composer and
autocomplete, then start the turn.

- [ ] **Step 7: Run input tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_tui_widgets.py tests/test_tui.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit input handling**

```bash
git add pitagora/cli/tui.py pitagora/cli/tui_widgets.py tests/test_tui.py tests/test_tui_widgets.py
git commit -F - <<'EOF'
feat(tui): add multiline composer and history

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
EOF
```

## Task 10: Render events and run controller turns off the UI thread

**Files:**
- Modify: `pitagora/cli/tui.py`
- Modify: `pitagora/cli/tui_widgets.py`
- Modify: `tests/test_tui.py`

- [ ] **Step 1: Write failing rendering and busy-state tests**

Add a blocking fake controller and tests:

```python
import threading

from rich.table import Table


class EventController(FakeController):
    def handle_input(self, text):
        table = Table()
        table.add_column("Value")
        table.add_row("42")
        return iter(
            [
                ChatEvent("user", text),
                ChatEvent("status", "Thinking..."),
                ChatEvent("markdown", "Result\n\n$$x^2$$"),
                ChatEvent("renderable", table),
                ChatEvent("comprehension", 0.75),
                ChatEvent(
                    "subconcepts",
                    [{"name": "Squares", "mastery": 0.8, "visited": True}],
                    {"current_index": 0},
                ),
                ChatEvent("controls"),
                ChatEvent("state_changed", metadata={"context": self.context}),
            ]
        )


class BlockingController(FakeController):
    def __init__(self):
        super().__init__()
        self.release = threading.Event()

    def handle_input(self, text):
        self.received.append(text)
        self.release.wait(timeout=2)
        return iter([ChatEvent("markdown", "done")])


@pytest.mark.asyncio
async def test_events_render_as_distinct_widgets():
    app = PitagoraApp(controller=EventController())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("h", "i", "enter")
        await pilot.pause()
        text = app.query_one("#conversation").renderable_text
        assert "△ you>" in text
        assert "Result" in text
        assert "(1)" in text
        assert "42" in text
        assert "75.0% comprehension" in text
        assert "[n] next" in text


@pytest.mark.asyncio
async def test_clear_visible_keeps_controller_context():
    controller = EventController()
    app = PitagoraApp(controller=controller)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("h", "i", "enter")
        await pilot.pause()
        await pilot.press("ctrl+l")
        assert "Result" not in app.query_one("#conversation").renderable_text
        assert controller.context["topic"] == "limits"


@pytest.mark.asyncio
async def test_busy_state_rejects_second_submission():
    controller = BlockingController()
    app = PitagoraApp(controller=controller)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("o", "n", "e", "enter")
        await pilot.pause()
        assert app.query_one("#composer").read_only is True
        app.submit_text("two")
        controller.release.set()
        await pilot.pause()
        assert controller.received == ["one"]
```

- [ ] **Step 2: Run tests and verify rendering failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_tui.py -q
```

Expected: new tests fail because event rendering and worker execution are
absent.

- [ ] **Step 3: Run turns in a Textual thread worker**

Use:

```python
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
```

Before starting, set `composer.read_only = True`, footer to busy, and reject a
second submission. `finish_turn()` restores input, footer, focus, and scrolls
to the bottom without animation.

Store the returned worker on `self._turn_worker`. Confirmed quit calls
`self._turn_worker.cancel()` when it is still running, then exits. Do not call a
worker-group API that is absent from Textual 0.38.

- [ ] **Step 4: Render each event kind**

`render_event()` does the following:

- `user`: mount a user message with dim `△ you>` label;
- `markdown`: call `split_math`, mount Textual `Markdown` for text pieces and
  cyan-bordered `EquationWidget` for display equations;
- `renderable`: mount `Static(event.content, expand=True)`;
- `error`: mount a red error `Static`;
- `status`: update footer while busy, or mount verification/status text;
- `comprehension`: mount `build_comprehension_gauge`;
- `subconcepts`: mount compact `build_subconcept_progress`;
- `controls`: mount `build_controls`;
- `state_changed`: refresh header/sidebar and call `exit()` when `quit` is set.

Every mounted message receives a role-specific class. Markdown and Rich
renderables use full available width.

- [ ] **Step 5: Add quit confirmation and clear action**

`action_request_quit()` pushes `QuitScreen` only when
`controller.context["teaching"]` is true. Otherwise it exits. A confirmed quit
cancels `self._turn_worker` when present and exits. Bind both `escape` and
`ctrl+c` to this action. If autocomplete is open, Escape closes it and stops
before the app-level action.

`action_clear_visible()` removes conversation children, mounts one dim
`Conversation cleared visually.` line, and focuses composer. It does not send
`/clear` and does not alter controller messages.

- [ ] **Step 6: Run TUI and controller tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_tui.py \
  tests/test_tui_widgets.py \
  tests/test_chat_controller.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit event rendering**

```bash
git add pitagora/cli/tui.py pitagora/cli/tui_widgets.py tests/test_tui.py
git commit -F - <<'EOF'
feat(tui): render async chat and teaching events

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
EOF
```

## Task 11: Polish documentation and validate the complete change

**Files:**
- Modify: `README.md:20-33`
- Modify: `tests/test_cli_app.py`
- Verify: all changed files

- [ ] **Step 1: Document installation and fallback**

Update installation examples:

```bash
# Core CLI and Rich fallback
pip install pitagora

# Full-screen Textual chat
pip install 'pitagora[tui]'

# All optional features
pip install 'pitagora[all]'
```

Document that `pitagora` launches the TUI in a terminal, while
`pitagora --simple` and `pitagora chat --simple` launch the Rich REPL.

- [ ] **Step 2: Add end-to-end Typer option tests**

Append:

```python
def test_chat_help_shows_simple_option(runner):
    result = runner.invoke(app, ["chat", "--help"])
    assert result.exit_code == 0
    assert "--simple" in result.stdout


def test_root_help_shows_simple_option(runner):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--simple" in result.stdout
```

- [ ] **Step 3: Run focused CLI tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli_app.py tests/test_cli_commands.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Run formatting and static checks**

Run:

```bash
.venv/bin/python -m ruff check \
  pitagora/chat.py \
  pitagora/chat_controller.py \
  pitagora/cli/app.py \
  pitagora/cli/rich_ui.py \
  pitagora/cli/tui.py \
  pitagora/cli/tui_widgets.py \
  pitagora/teaching/ui.py \
  tests/test_chat_controller.py \
  tests/test_cli_app.py \
  tests/test_tui.py \
  tests/test_tui_widgets.py
.venv/bin/python -m black --check \
  pitagora/chat.py \
  pitagora/chat_controller.py \
  pitagora/cli/app.py \
  pitagora/cli/rich_ui.py \
  pitagora/cli/tui.py \
  pitagora/cli/tui_widgets.py \
  pitagora/teaching/ui.py \
  tests/test_chat_controller.py \
  tests/test_cli_app.py \
  tests/test_tui.py \
  tests/test_tui_widgets.py
```

Expected: both commands pass. If Black reports changes, run it on the same
paths, inspect the diff, then rerun both checks.

- [ ] **Step 5: Run the required full suite**

Run:

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 6: Run manual smoke checks**

Run:

```bash
.venv/bin/pitagora --help
.venv/bin/pitagora chat --help
printf '/quit\n' | .venv/bin/pitagora --simple
```

Expected: both help commands list `--simple`; piped simple mode exits cleanly
without entering alternate screen.

In a real terminal, run:

```bash
.venv/bin/pitagora
```

Verify startup banner, fixed composer, Enter and Shift+Enter, `/help`
autocomplete, `Ctrl+B`, resize at 80 and 120 columns, `Ctrl+X`, `/explore
limits`, immediate teaching shortcut, `Ctrl+L`, and quit confirmation.

- [ ] **Step 7: Review the final diff and scan for secrets**

Run:

```bash
git status --short --branch
git diff --check
git diff --stat
git diff
```

Invoke the `commit-security-scan` skill before the final commit. Expected: no
secrets, credentials, unrelated files, or whitespace errors.

- [ ] **Step 8: Commit documentation and final fixes**

```bash
git add README.md tests/test_cli_app.py
git commit -F - <<'EOF'
docs(tui): document full-screen chat

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
EOF
```

If validation changed implementation files after their task commit, stage only
those reviewed changes and include them in this final commit.

- [ ] **Step 9: Push the validated branch**

Review `git status --short --branch` and `git log --oneline -10` immediately
before pushing. Then:

```bash
git push origin main
```

Expected: remote `main` advances to the validated local commits. Do not force
push.
