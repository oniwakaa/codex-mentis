# Pitagora — Coding Agent Implementation Brief

## Context

You are working on the **Pitagora** project (formerly "Codex Mentis"), an interactive teaching harness for mathematics, physics, and philosophy. The repo is at `~/projects/codex-mentis/`.

Read `ROADMAP_PITAGORA.md` in the repo root for the full product design. This brief covers what to implement.

**Already done** (committed): ASCII banner, gold theme, styled prompt (`△ pitagora>`), rebranded system prompt in chat.py, `show_pitagora_banner()` and `show_welcome()` in rich_ui.py.

---

## TASK 1: Full Package Rename (codex_mentis → pitagora)

Rename the Python package from `codex_mentis` to `pitagora`. This affects:

1. **Directory**: `codex_mentis/` → `pitagora/`
2. **Every import** in every `.py` file: `from codex_mentis.` → `from pitagora.`
3. **pyproject.toml**: name, entry points, package dirs
4. **Config directory**: `~/.codex-mentis/` → `~/.pitagora/` (update all references in code — there are ~15 occurrences across config.py, chat.py, spaced_repetition.py, etc.)
5. **Test files**: all 4 root-level test files + all 20 files under `tests/` — update imports
6. **YAML workflow files**: update any agent name references if they reference the package
7. **README.md, ANALYSIS.md, ARCHITECTURE.md, INTEGRATION.md**: update all mentions
8. **__init__.py, __main__.py**: update references
9. **data/default_config.yaml**: no changes needed (it's config values, not package refs)

**Approach**: Do a global search-and-replace. Be careful with:
- `codex_mentis` in strings (error messages, config paths) — these should become `pitagora`
- `codex-mentis` in CLI help text — these should become `pitagora`
- `Codex Mentis` in display strings — these should become `Pitagora`
- `CM_MODEL` env var — rename to `PITAGORA_MODEL`

**Verification**: After rename, run `python -m pytest tests/ -x` to ensure imports resolve.

---

## TASK 2: Teaching Session Engine (THE CORE FEATURE)

This is the most important new feature. The current `chat.py` REPL is a basic message-response loop. We need an **interactive teaching mode** where the agent guides the user through topics with back-and-forth dialogue.

### 2a: TeachingSession class

Create `pitagora/teaching/session.py`:

```python
class TeachingSession:
    """Interactive teaching session with state machine."""
    
    # States
    INTRODUCING = "introducing"   # Agent presents the topic overview
    EXPLORING = "exploring"       # Agent explains a sub-concept
    CHECKING = "checking"         # Agent asks a question to verify understanding
    ADAPTING = "adapting"         # Agent adjusts based on user response
    VISUALIZING = "visualizing"   # Agent shows a visualization
    QUIZZING = "quizzing"         # Agent presents a practice problem
    REVIEWING = "reviewing"       # Agent reviews what was learned
    PAUSED = "paused"             # Session paused (save state)
    
    def __init__(self, topic: str, user_level: str = "intermediate"):
        self.topic = topic
        self.user_level = user_level
        self.state = self.INTRODUCING
        self.comprehension_score = 0.5  # 0.0 to 1.0
        self.interaction_history = []   # List of (action, user_response, analysis)
        self.sub_concepts = []          # Ordered list of sub-concepts to cover
        self.current_sub_concept_idx = 0
        self.style_effectiveness = {    # Track which explanation styles work
            "feynman": 0.5, "formal": 0.5, "visual": 0.5,
            "historical": 0.5, "socratic": 0.5, "applied": 0.5
        }
        self.journey_id = None          # Link to persistent journey
    
    def next_action(self) -> dict:
        """Determine the next teaching action based on state."""
        # Returns {"type": "explain"|"question"|"visualize"|"quiz"|"review",
        #          "style": "feynman"|"formal"|..., 
        #          "prompt_hint": "...",
        #          "sub_concept": "..."}
    
    def analyze_response(self, user_input: str) -> dict:
        """Classify user response and update state."""
        # Returns {"classification": "correct"|"partial"|"confused"|"skip"|"deeper"|"question",
        #          "comprehension_delta": float,
        #          "suggested_style": str,
        #          "next_state": str}
    
    def adapt_difficulty(self, analysis: dict) -> None:
        """Adjust teaching approach based on response analysis."""
        # If comprehension trending up → advance to next sub-concept
        # If trending down → simplify, switch to more intuitive style
        # If "deeper" → add mathematical rigor
        # If "skip" → advance but flag for review
    
    def save(self) -> dict:
        """Serialize session state for persistence."""
    
    @classmethod
    def load(cls, data: dict) -> 'TeachingSession':
        """Restore session from saved state."""
```

### 2b: Response Analyzer

Create `pitagora/teaching/analyzer.py`:

The analyzer uses the LLM (via chat_completion) to classify user responses. **Do NOT use keyword matching** — use a lightweight LLM call with a classification prompt.

```python
class ResponseAnalyzer:
    """Analyzes user responses during teaching sessions."""
    
    CLASSIFICATION_PROMPT = """Analyze this student response in a teaching session about {topic}.
    
Student said: "{response}"
Previous concept being explained: "{concept}"

Classify as ONE of:
- correct: Student demonstrates understanding
- partial: Student gets some parts but is confused about others
- confused: Student is clearly lost
- skip: Student wants to move on
- deeper: Student wants more detail/rigor
- question: Student is asking a clarifying question
- off_topic: Student changed the subject

Respond with ONLY the classification word, then a brief explanation on the next line."""

    def classify(self, user_input: str, context: dict) -> dict:
        """Send classification prompt to LLM and parse response."""
```

### 2c: Teaching-Aware Chat Integration

Modify `pitagora/chat.py` to support teaching mode:

1. Add `/explore <topic>` command that creates a TeachingSession
2. When in teaching mode, every user message goes through the ResponseAnalyzer
3. After each response, the TeachingSession determines the next action
4. The next action generates a specialized prompt for the LLM
5. Display interaction controls after each agent message:
   ```
   [n] Next  [e] Explain differently  [d] Go deeper  [?] I'm confused  [s] Skip
   ```
6. Short commands (`n`, `e`, `d`, `s`) are translated to analysis signals before processing
7. `/explore --continue` resumes a saved teaching session
8. `/dashboard` shows active learning journeys

### 2d: Interaction Control Display

Create `pitagora/teaching/ui.py` for teaching-specific Rich widgets:

```python
def show_teaching_controls(state: str) -> None:
    """Show interactive controls based on current teaching state."""
    # Renders a styled line like:
    # [n] Next  [e] Explain differently  [d] Go deeper  [?] I'm confused  [s] Skip

def show_comprehension_gauge(score: float) -> None:
    """Show a visual comprehension indicator."""
    # Renders: Understanding: [████████░░] 80%

def show_journey_map(session: TeachingSession, concept_graph) -> None:
    """Show the teaching journey as a concept tree with progress."""
    # Uses Rich Tree with color-coded nodes (green=mastered, yellow=current, dim=upcoming)

def show_sub_concept_progress(current: int, total: int, name: str) -> None:
    """Show progress through sub-concepts."""
    # Renders: ▸ 3/7: Understanding the Lagrangian
```

---

## TASK 3: Learning Journeys (Persistent Progress)

Create `pitagora/journeys/`:

### 3a: Journey Model

Create `pitagora/journeys/model.py`:

```python
@dataclass
class LearningJourney:
    id: str                      # UUID
    topic: str                   # e.g. "Lagrangian Mechanics"
    status: str                  # "active", "paused", "completed"
    started_at: str              # ISO timestamp
    last_active: str             # ISO timestamp
    user_level: str              # "beginner", "intermediate", "advanced"
    sub_concepts: List[dict]     # [{name, status, mastery_score, interactions_count}]
    current_idx: int             # Index into sub_concepts
    comprehension_history: List[dict]  # [{timestamp, score, sub_concept}]
    style_effectiveness: dict    # {style_name: float}
    total_interactions: int
```

### 3b: Journey Store

Create `pitagora/journeys/store.py`:

- Save/load journeys as JSON files in `~/.pitagora/journeys/`
- `save_journey(journey)`, `load_journey(id)`, `list_journeys()`, `delete_journey(id)`
- Auto-save after every interaction

### 3c: Journey Commands

Add to the CLI and chat REPL:
- `/explore <topic>` — start new journey or resume existing one for that topic
- `/explore --continue [id]` — resume a specific journey
- `/journeys` — list all journeys with progress
- `/dashboard` — visual overview of all learning progress

---

## TASK 4: Philosophy Domain

### 4a: Add Philosophy Concepts

Add to `pitagora/data/concepts.yaml` (or `codex_mentis/data/concepts.yaml` before rename):

```yaml
philosophy:
  - id: phil_logic
    name: Formal Logic
    prerequisites: []
  - id: phil_propositional
    name: Propositional Logic
    prerequisites: [phil_logic]
  - id: phil_predicate
    name: Predicate Logic
    prerequisites: [phil_propositional]
  - id: phil_modal
    name: Modal Logic
    prerequisites: [phil_predicate]
  - id: phil_epistemology
    name: Epistemology
    prerequisites: [phil_logic]
  - id: phil_metaphysics
    name: Metaphysics
    prerequisites: [phil_epistemology]
  - id: phil_ethics
    name: Ethics
    prerequisites: [phil_epistemology]
  - id: phil_philosophy_of_math
    name: Philosophy of Mathematics
    prerequisites: [phil_epistemology, calc_limits]
  - id: phil_philosophy_of_science
    name: Philosophy of Science
    prerequisites: [phil_epistemology]
  - id: phil_aesthetics
    name: Aesthetics
    prerequisites: [phil_metaphysics]
```

### 4b: Philosophy Workflow

Create `pitagora/data/workflows/philosophical_reasoning.yaml`:

A workflow for reasoning about philosophical questions:
1. **Clarify** — Define terms, identify the thesis
2. **Argue** — Build the strongest argument FOR
3. **Challenge** — Build the strongest argument AGAINST (adversarial)
4. **Synthesize** — Find the resolution or deeper understanding
5. **Connect** — Link to mathematical/scientific concepts where relevant

### 4c: Philosophy Skills

Create `pitagora/skills/builtin/logic.yaml` — skill definitions for formal logic topics (propositional calculus, truth tables, natural deduction, etc.)

---

## TASK 5: Visualization Improvements

### 5a: Enhanced Concept Map

Improve `print_concept_map` in `rich_ui.py` to show:
- Mastery colors (green ≥ 0.8, yellow ≥ 0.5, red < 0.5, dim = not started)
- Current position marker (▸) for active teaching sessions
- Prerequisite arrows (show dependencies, not just children)

### 5b: Equation Block Renderer

Add to `rich_ui.py`:

```python
def show_equation_block(equations: list, title: str = "") -> None:
    """Render a sequence of equations as a derivation block.
    
    Each equation gets a step number and optional annotation.
    Uses Rich panels with monospace + Unicode math symbols.
    """
```

### 5c: Mastery Dashboard

Add to `rich_ui.py`:

```python
def show_mastery_dashboard(concept_graph, mastery_tracker) -> None:
    """Show a visual mastery overview by domain.
    
    Groups concepts by domain (algebra, calculus, physics, philosophy...)
    Shows a progress bar per domain with mastered/total counts.
    """
```

---

## TASK 6: Bug Fixes & Missing Features

Please audit the codebase and fix:

1. **Orchestrator is dead code**: `agents/orchestrator.py` exists but `chat.py` bypasses it entirely — it calls `chat_completion()` directly. The orchestrator should be integrated into the chat flow for multi-agent workflows (derive_and_prove, teach, etc.) to actually work from the REPL. At minimum, add a `/workflow <name> <args>` command that runs a workflow through the orchestrator.

2. **MCP stubs**: `mcp_integration/__init__.py` is empty. Either implement or remove.

3. **TUI widgets**: `cli/widgets/__init__.py` is empty. Either implement or remove.

4. **Session save/load**: The `/save` and `/resume` commands in chat.py use `sessions.py` but check if `save_session` and `load_session` actually work end-to-end.

5. **Config path consistency**: Some files use `~/.codex-mentis/` directly (string literal), others use `CONFIG_DIR` from `core/config.py`. After rename, ensure ALL config paths go through a single `PITAGORA_DIR` constant.

6. **Test coverage**: After rename, ensure all tests pass. Add tests for:
   - TeachingSession state machine
   - ResponseAnalyzer classification
   - LearningJourney save/load
   - Philosophy concepts loading

7. **Missing `__init__.py` exports**: Check that `pitagora/__init__.py` exports key classes.

8. **Error handling in chat.py**: The `_verify_math` function silently catches all exceptions. Make it more robust.

---

## Implementation Order

1. **TASK 1** (rename) — Do this FIRST. Everything else builds on it.
2. **TASK 2a-2b** (TeachingSession + ResponseAnalyzer) — Core logic
3. **TASK 3** (Learning Journeys) — Persistence layer
4. **TASK 2c-2d** (Chat integration + UI) — Wire it all together
5. **TASK 4** (Philosophy) — New domain
6. **TASK 5** (Visualization) — Polish
7. **TASK 6** (Bugs) — Fix throughout

## Constraints

- **Provider**: CLIProxy at `http://localhost:8317/v1` with `cliproxy-sk-local` key. Model: `google/gemini-3.6-flash-high`. This is an OpenAI-compatible API.
- **No new heavy dependencies**. Use what's already in pyproject.toml (rich, httpx, pydantic, sqlite-utils, sympy, plotext, pyyaml).
- **Tests must pass**: Run `python -m pytest tests/ -x` after each major change.
- **Don't break the existing chat REPL**: All new features should be additive. The default chat mode should still work as a free-form Q&A.
- **Config dir**: `~/.pitagora/` after rename.
- **DB files**: `~/.pitagora/memory.db` for spaced repetition, `~/.pitagora/journeys/` for journey JSON files.
