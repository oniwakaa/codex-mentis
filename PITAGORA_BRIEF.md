# Pitagora — Implementation Brief

## Setup

Clone the repo and work locally:
```
git clone https://github.com/oniwakaa/codex-mentis.git
cd codex-mentis
```

Read ROADMAP_PITAGORA.md for the full product vision. This brief is the actionable task list.

**Already done** (committed, don't redo): ASCII banner in gold, `show_pitagora_banner()` and `show_welcome()` in `rich_ui.py`, styled prompt `△ pitagora>`, rebranded system prompt in `chat.py`.

**Provider**: CLIProxy at `http://localhost:8317/v1`, key `cliproxy-sk-local`, model `google/gemini-3.6-flash-high` (OpenAI-compatible API). No new heavy dependencies — use what's already in pyproject.toml.

---

## TASK 1: Full Package Rename — DO FIRST

Rename the entire Python package from `codex_mentis` to `pitagora`:

- Rename the directory `codex_mentis/` → `pitagora/`
- Replace every `from codex_mentis` / `import codex_mentis` with `from pitagora` / `import pitagora` across all .py files (~50 modules + ~24 test files)
- Update pyproject.toml: package name, entry points, package directories
- Update all config directory paths from `~/.codex-mentis/` to `~/.pitagora/` — there are ~15 string literals across config.py, chat.py, spaced_repetition.py, store.py, etc.
- Replace display strings: "Codex Mentis" → "Pitagora", "codex-mentis" (in CLI help/errors) → "pitagora"
- Rename env var `CM_MODEL` → `PITAGORA_MODEL`
- Update all docs (README.md, ANALYSIS.md, ARCHITECTURE.md, INTEGRATION.md)
- Ensure all config paths flow through a single constant (create one in `core/constants.py` if needed) instead of hardcoding `~/.pitagora/` in each file
- Run `python -m pytest tests/ -x` after — all tests must pass

---

## TASK 2: Teaching Session Engine — THE CORE FEATURE

The current chat REPL (`chat.py`) is a basic ask→answer loop. It needs to become an interactive teaching system where the agent guides users through topics with back-and-forth dialogue, adapting to their responses.

### What to build:

**TeachingSession** (`pitagora/teaching/session.py`): A state machine that manages an interactive teaching session. States: introducing → exploring ↔ checking ↔ adapting → visualizing / quizzing → reviewing → completed (any state can pause). It tracks: current topic, sub-concepts to cover (ordered list), current sub-concept index, comprehension score (0.0-1.0), interaction history, style effectiveness (which explanation styles work best — feynman, formal, visual, historical, socratic, applied). It supports user shortcuts: n=next, e=explain differently, d=go deeper, s=skip, ?=confused, v=visualize, q=quiz. Must be serializable (save/load) for session persistence.

**ResponseAnalyzer** (`pitagora/teaching/analyzer.py`): Classifies user responses using LLM calls (NOT keyword matching). Classifications: correct, partial, confused, skip, deeper, question, off_topic. Has a fast path for single-character shortcuts that bypasses the LLM. Each classification maps to a comprehension delta (correct=+0.15, confused=-0.2, etc.). Uses the same chat_completion function the rest of the app uses.

**Teaching UI** (`pitagora/teaching/ui.py`): Rich widgets for the teaching experience — interactive controls display ([n] Next [e] Explain differently [d] Go deeper etc.), comprehension gauge (progress bar with color), sub-concept progress indicator, topic overview panel (showing what we'll cover, prerequisites, level), session summary (what was mastered, best style, interaction count), journey map (concept tree with mastery colors).

**Chat integration** (modify `chat.py`): Add `/explore <topic>` command that creates a TeachingSession, generates sub-concepts (from concept graph if available, or via LLM), shows a topic overview, then enters teaching mode. In teaching mode, every user message goes through the ResponseAnalyzer, the TeachingSession determines the next action, and a teaching-specific prompt is built (including style instructions, comprehension context, sub-concept info). Show controls after each agent message. Support `/explore --continue` to resume. Add `/journeys` and `/dashboard` commands. The default free-form chat mode must still work untouched.

---

## TASK 3: Learning Journeys — Persistent Progress

**Journey model** (`pitagora/journeys/model.py`): A dataclass representing a persistent learning journey — id, topic, status (active/paused/completed/abandoned), timestamps, user level, sub-concepts with mastery scores, comprehension history, style effectiveness, total interactions, and the serialized TeachingSession state for resume.

**Journey store** (`pitagora/journeys/store.py`): Save/load/list/delete journeys as JSON files in `~/.pitagora/journeys/`. Auto-save after every interaction during teaching.

**Wire into chat**: `/explore` auto-creates a journey or resumes an existing one for the same topic. `/journeys` lists all with status icons. `/dashboard` shows a visual overview.

---

## TASK 4: Philosophy Domain

**Concepts**: Add a `philosophy` section to `data/concepts.yaml` with: Formal Logic (no prereqs), Propositional Logic (needs logic), Predicate Logic (needs propositional), Modal Logic (needs predicate), Epistemology (needs logic), Metaphysics (needs epistemology), Ethics (needs epistemology), Philosophy of Mathematics (needs epistemology + calc_limits), Philosophy of Science (needs epistemology), Aesthetics (needs metaphysics).

**Workflow**: Create `data/workflows/philosophical_reasoning.yaml` — a 5-step pipeline: clarify (define terms, identify assumptions) → argue_for (build strongest argument for the thesis) → argue_against (adversarial challenge with counter-examples) → synthesize (find common ground, crux of disagreement, nuanced position) → connect (link to math/science/other philosophical traditions/history).

**Skill**: Create `skills/builtin/logic.yaml` covering truth tables, natural deduction (modus ponens, modus tollens, hypothetical syllogism), and predicate calculus (quantifiers), each with beginner/intermediate/advanced exercises.

---

## TASK 5: Visualization Improvements

**Enhanced concept map**: The existing `print_concept_map` in `rich_ui.py` needs mastery colors — green (≥0.8), yellow (≥0.5), red (<0.5), dim (not started). Add a current concept marker (▸). Accept mastery_scores dict and current_concept params.

**Equation block renderer**: New function in `rich_ui.py` that renders a sequence of numbered equations in a Rich panel, each with an optional annotation. The existing `print_math` function should support returning a string instead of printing (add a return_str parameter).

**Mastery dashboard**: New function in `rich_ui.py` that shows a Rich table grouped by domain (algebra, calculus, physics, philosophy...) with columns for total concepts, mastered count, progress bar, and status. Show active journeys below the table.

---

## TASK 6: Bug Fixes & Audit

**Dead orchestrator**: `agents/orchestrator.py` exists but chat.py bypasses it. Add a `/workflow <name> [args]` command that instantiates the orchestrator with all agents (explainer, tutor, prover, reviewer, visualizer, researcher, debate) and runs the named workflow. Available workflows: teach, derive_and_prove, concept_mastery, debate, deep_research, philosophical_reasoning.

**Empty stubs**: `mcp_integration/__init__.py` and `cli/widgets/__init__.py` are empty. Either implement something useful or add a docstring explaining they're reserved for future use.

**Config consistency**: After rename, audit that no file hardcodes `~/.pitagora/` as a string — everything should import from a single constant.

**Session persistence**: Verify that `/save` and `/resume` in chat.py actually work end-to-end with `sessions.py`. Fix if broken.

**New tests**: Add tests for TeachingSession (state transitions, save/load, shortcuts, comprehension tracking), ResponseAnalyzer (shortcut classification, fallback), LearningJourneys (save/load/list/delete), and philosophy concepts loading from YAML.

**Error handling**: The `_verify_math` function in chat.py silently catches all exceptions — make it more robust with logging.

---

## Implementation Order

1. TASK 1 (rename) — everything depends on this
2. TASK 2 (teaching engine) — core feature, build the classes first then wire into chat
3. TASK 3 (journeys) — persistence for the teaching engine
4. TASK 4 (philosophy) — new domain
5. TASK 5 (visualization) — polish
6. TASK 6 (bugs) — fix throughout

Run `python -m pytest tests/ -x` after each task. Commit after each completed task.
