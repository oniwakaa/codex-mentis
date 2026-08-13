# Pitagora TUI overhaul design

## Goal

Replace the default line-oriented chat experience with a full-screen Textual
application while preserving the existing Rich REPL as the `--simple` and
non-TTY fallback. Both frontends must use the same chat and teaching behavior.

The finished interface has:

- a fixed PITAGORA header;
- a scrollable conversation;
- a dedicated multiline composer;
- a responsive context sidebar;
- Markdown, equations, Rich tables, plots, concept maps, and teaching widgets;
- non-blocking model calls; and
- no flicker or layout jumps during normal use.

## Scope

This change covers the interactive chat entry points, shared chat behavior,
terminal rendering, input handling, responsive sidebar, packaging, and tests.
It does not add browser plots, Plotly, Matplotlib integration beyond what the
project already has, persistent TUI input history, or new teaching logic.

## Architecture

### Shared controller

Add `pitagora/chat_controller.py`. `ChatController` owns:

- provider configuration and model selection;
- mode, topic, system prompt, and conversation messages;
- slash-command dispatch;
- free-form RAG-enriched turns;
- math verification and memory recording;
- teaching session, analyzer, journey, and feedback-loop state; and
- session statistics used by the sidebar.

The controller does not import Textual or print to a console. It accepts user
input and emits a short stream or list of `ChatEvent` values. One event type is
enough:

```python
@dataclass
class ChatEvent:
    kind: str
    content: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Supported event kinds are `user`, `markdown`, `status`, `error`, `renderable`,
and `state_changed`. A command mutates controller state once, then emits events
for either frontend.

### Rich fallback adapter

`pitagora/chat.py` keeps its public provider, RAG, verification, memory, and
teaching helper functions. `launch_chat()` becomes a Rich adapter around
`ChatController`: read with `pitagora_prompt()`, pass input to the controller,
and print returned events.

The fallback retains the current prompt-toolkit input bar, slash commands,
command text, teaching shortcuts, persistence, and error behavior. This is the
path used by `--simple`, pipes, CI, and installations without Textual.

### Textual adapter

Add `pitagora/cli/tui.py` with `PitagoraApp(App)`. It owns only presentation and
interaction:

- widget composition and CSS;
- input history and autocomplete;
- keybindings and focus;
- worker lifecycle;
- rendering controller events; and
- responsive layout.

Synchronous controller work runs through a Textual worker and
`asyncio.to_thread()`. Only one turn may run at a time. This prevents duplicate
sends and concurrent mutation of messages or teaching state.

## CLI and dependency behavior

Both `pitagora` and `pitagora chat` default to the Textual app when stdin and
stdout are interactive terminals.

Both entry points accept `--simple`. The old Rich adapter runs when:

- `--simple` is present;
- stdin or stdout is not a TTY; or
- importing Textual fails.

When Textual is missing in an interactive terminal, print a one-line
`pip install pitagora[tui]` hint before falling back. Textual imports remain
inside the TUI launch path, so other commands never require it.

The existing first-run setup wizard still runs before either chat frontend.

Move Textual out of core dependencies:

```toml
[project.optional-dependencies]
tui = ["textual>=0.38.0"]
```

`TextArea` was introduced in Textual 0.38.0, so 0.30 cannot support the
specified composer. The existing `all` extra includes the same Textual
requirement.

## Application shell

The app uses the terminal's alternate screen.

### Header

A fixed one-line header uses deep indigo (`#1a1a3e`). The left side shows a
bold gold triangle and `PITAGORA`. The right side shows mode, topic, and model,
truncated safely on narrow terminals.

### Main area

The main row fills all remaining height. A `VerticalScroll` conversation takes
the available width. Each message has horizontal padding and separation from
the next message.

At widths of 100 columns or more, a 28-column `ContextSidebar` appears at the
right. Below 100 columns it is hidden by default. `Ctrl+B` opens it as an
overlay, so an 80-column terminal keeps enough room for equations and code.

### Composer

A fixed four-line composer sits at the bottom. It contains a bold green
`△ pitagora>` prefix and a custom `ChatTextArea`. Border and background changes
separate it from conversation content. Focus returns to the composer after
every completed or failed turn.

A footer shows current worker state and short key hints.

### Compact mode

`Ctrl+X` toggles full and compact TUI layouts. Compact mode hides sidebar,
reduces message spacing, and shortens metadata in the header. It does not exit
Textual or transfer the session to the Rich REPL.

## Startup

On mount, the conversation receives:

1. a six-line or taller triangle/PITAGORA ASCII banner in gold;
2. `Think. Prove. Understand.` beneath it; and
3. a welcome panel containing current model, active journeys, and due reviews.

The app then focuses the composer. The welcome content stays in conversation
history. There is no timed splash screen or animation that moves the layout.

## Input behavior

`ChatTextArea` implements:

- Enter sends all composer text;
- Shift+Enter inserts a newline;
- multiline paste remains one message;
- Up and Down navigate up to 100 in-memory entries when the cursor is at the
  first or last logical line;
- Tab opens or accepts slash-command completion; and
- Escape closes autocomplete before applying the app-level quit binding.

The existing `COMMAND_TREE` remains the command source. Typing `/` at the start
of an empty composer opens a small `OptionList` popup. Filtering follows typed
text, and accepting an option inserts it into the composer.

In active teaching mode, pressing one of `n/e/d/s/?/v/q/p` while the composer is
empty dispatches that shortcut immediately. Other input remains normal
multiline text.

## Keybindings

| Key | Action |
| --- | --- |
| Enter | Send message |
| Shift+Enter | Insert newline |
| Escape | Close popup, otherwise quit |
| Ctrl+C | Quit |
| Ctrl+L | Clear visible conversation, keep controller context, focus composer |
| Ctrl+B | Toggle inline sidebar or narrow overlay |
| Ctrl+X | Toggle full and compact TUI layouts |
| Tab | Open or accept slash completion |
| Up/Down | Navigate input history at text boundaries |

Quit is immediate outside an active teaching session. During an active
teaching session, Escape or Ctrl+C opens a confirmation modal so work is not
abandoned accidentally.

## Rendering

### Markdown

Assistant and user text use Textual's Markdown widget. Code fences retain Rich
syntax highlighting. User messages use a dim `△ you>` label and a distinct
background. Assistant messages use the normal content background.

### Equations

Split display math (`$$...$$`) from surrounding Markdown. Render each display
equation through the existing LaTeX-to-Unicode path, centered in a full-width
cyan-bordered widget. Number display equations per assistant response.

Convert inline math (`$...$`) through the same Unicode helper before handing
the surrounding text to Markdown. If conversion fails, show the original
LaTeX rather than dropping content.

### Rich renderables

Existing formatting modules gain small `build_*()` functions that return Rich
renderables. Existing `print_*()` and `show_*()` functions call those builders
and continue printing to their passed console. This keeps one visual
implementation and lets Textual mount the returned objects in `Static`
widgets.

Tables use the available content width and alternate row styles. Concept maps
are wrapped in titled panels. Plotext output is captured into a titled,
bordered terminal panel. Browser opening is outside this phase.

### Teaching mode

Each teaching response renders in this order:

1. Markdown response;
2. compact horizontal comprehension bar;
3. one-line sub-concept progress;
4. teaching controls line.

The sidebar reads from the same `TeachingSession`; no second mastery model is
introduced.

## Sidebar

The sidebar shows:

- current topic and mode;
- comprehension score and colored progress bar;
- sub-concepts with green, yellow, red, or unvisited indicators;
- active journey name and progress;
- due review count;
- messages sent in this session; and
- elapsed session time.

Sidebar reads must be cheap and best-effort. Journey and review lookups happen
at startup or after relevant state changes, not every render.

## Errors and cancellation

Provider and network failures become visible error events in conversation.
Command and persistence failures keep their current graceful fallback behavior.
An unexpected worker exception adds a red notice, clears busy state, and
returns focus to the composer.

The app disables message submission while a turn runs. Confirmed quit cancels
the UI worker and exits. Controller persistence operations already in progress
are allowed to finish when cancellation cannot safely interrupt them.

## Testing

Run `pytest tests/ -q` before implementation to establish the baseline.

Add controller tests for:

- free-form message enrichment and event output;
- slash-command state changes;
- teaching start, shortcut, pause, and save behavior;
- provider failures; and
- session and journey commands.

Add Textual tests with `App.run_test()` for:

- shell mount and initial focus;
- send, multiline input, paste, and 100-entry history;
- slash autocomplete;
- sidebar breakpoint, overlay, and toggle;
- compact layout;
- async response rendering and busy state; and
- teaching gauge, progress, and controls.

Add CLI tests proving:

- interactive default selects Textual;
- `--simple` selects the Rich adapter;
- non-TTY input selects the Rich adapter; and
- missing Textual prints the install hint and falls back without crashing.

Run focused tests while implementing, then the full suite. Before committing,
review the diff for accidental changes and secrets. Commit the implementation
and push it to the configured remote.

## Acceptance criteria

1. `pitagora` in a TTY opens the full-screen Textual app.
2. Startup shows a large triangle/PITAGORA banner and tagline.
3. Input stays in the fixed composer at the bottom.
4. Conversation is scrollable and renders Markdown, equations, Rich tables,
   plots, and concept maps cleanly.
5. `/explore` uses the existing teaching state machine and shows inline
   comprehension, progress, and controls.
6. Sidebar shows live context, toggles with `Ctrl+B`, and becomes an overlay
   below 100 columns.
7. `pitagora --simple` and `pitagora chat --simple` use the Rich REPL.
8. Resize updates layout without flicker or broken dimensions.
9. Existing tests pass, and focused controller/TUI tests cover the new paths.
