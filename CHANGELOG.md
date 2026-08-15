# Changelog

All notable changes to Pitagora are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-08-15

### Added

- **Model Context Protocol (MCP) Server Integration** — `pitagora/mcp/` (`server.py`, `tools.py`, `resources.py`) providing stdio JSON-RPC server with 4 tools and 3 resources.
- **Self-Improving Prompt Loop Hardening** — Versioned `prompt_revisions` table, prompt injection safety filter, and rollback command in `SelfImproverAgent`.
- **Homebrew Formula & Release Workflow** — `Formula/pitagora.rb` and `.github/workflows/release.yml` for PyPI and GitHub releases.
- **Security Audit & Hardening** — Path traversal checks with `.is_relative_to()`, masked API keys in `ProviderConfig.__repr__`, AST security validation, and `tests/test_security_audit.py`.
- **ReAct Agent Loop Engine** — 6-phase ReAct execution loop in `pitagora/agents/loop.py` with parallel read execution.
- **Tool Registry** — JSON Schema tool registration and permission dispatch in `pitagora/agents/tools/`.
- **Adaptive Context Compaction** — Context window sliding budget and tool result summarization in `pitagora/agents/context.py`.
- **Graduated Permission System** — 5-level escalation manager in `pitagora/agents/permissions.py`.
- **Textual TUI Application** — Full-screen Textual TUI in `pitagora/tui/` with interactive widgets and keybindings.
- **Multi-Provider Support** — Added `AnthropicProvider`, `OllamaProvider`, and `LMStudioProvider` implementations.
- **Agent Loop Safety Guards** — `LoopGuard` for max iterations, wall clock timeout, cost budget, and doom-loop detection.
- **Append-Only Session State** — Messages array as single source of truth in `pitagora/sessions.py`.
- **Docker Support** — Production `Dockerfile` and `.dockerignore`.

## [Unreleased]

### Added

- **Agent loop safety guards** — `LoopGuard` in `pitagora/agents/guards.py` for max iterations, timeout, cost budget, and doom-loop detection.
- **ReAct Agent Loop** — `AgentLoop` in `pitagora/agents/loop.py` implementing 6-phase lifecycle with parallel read execution.
- **Tool Registry** — `ToolRegistry` and `ToolSpec` in `pitagora/agents/tools/` with JSON schema validation and permission levels.
- **Adaptive Context Compaction** — `ContextManager` in `pitagora/agents/context.py` with sliding window and tool call summarization.
- **Graduated Permission System** — `PermissionManager` in `pitagora/agents/permissions.py` with 5-level escalation.
- **Textual TUI Migration** — Replaced legacy Rich TUI with full-screen Textual application in `pitagora/tui/`.
- **Streaming Token Display** — `stream_completion` in providers and live token velocity rendering.
- **Append-Only Session State** — Message array as single source of truth in `pitagora/sessions.py`.
- **Multi-Provider Fallback** — `AnthropicProvider`, `OllamaProvider`, and `LMStudioProvider` implementations.
- **Session metadata tracking** — token count, cost tracking, iteration count, and tool calls recording in `pitagora/sessions.py`.
- **Packaging and Docker support** — `Dockerfile` and `.dockerignore` for containerized execution.

### Changed

- **Consolidated test suite** — Removed legacy root test files (`test_legacy.py`, `test_new_agents.py`, `test_new_features_legacy.py`, `test_system_legacy.py`) and ported all assertions into `tests/`.
- **Modularized chat controller** — Refactored `chat_controller.py` into modular `pitagora/chat/` package (`controller.py`, `session.py`, `renderer.py`, `runtime.py`).

## [0.2.0] — 2026-08-14

### Added

- **Symbolic security sandbox** — AST-based `safe_parser.py` validates expressions
  before `sympify`; subprocess sandbox with resource limits, timeout, and
  restricted `__builtins__`.
- **Provider abstraction layer** — typed async `BaseProvider`, `OpenAIProvider`
  with transient-retry, `FallbackProvider` with token-cost accounting
  (`pitagora.agents.providers`).
- **Teaching session state machine** — pause / resume, comprehension scoring,
  multi-style classification in `teaching/session.py` and `teaching/analyzer.py`.
- **Journey persistence** — atomic writes, path-traversal protection, malformed-
  file recovery in `journeys/store.py`.
- **Memory hardening** — SQLite WAL mode, export / import, SM-2 quality
  verification in `memory/store.py` and `memory/spaced_repetition.py`.
- **Concept tracker improvements** — mastery decay, review-queue surfacing in
  `concepts/tracker.py`.
- **CLI commands** — `solve` (alias for `reason`), `dashboard`, `concept list`,
  `config set` for top-level scalars, `explore --continue JOURNEY_ID`.
- **CI pipeline** — GitHub Actions workflow (`ci.yml`) with Python 3.11 / 3.12
  matrix running ruff, black, mypy, pytest, and `uv build`.
- `tests/__init__.py` for reliable pytest collection.

### Changed

- Bumped version to **0.2.0**.
- `pyproject.toml` quality gates: ruff (E4/E7/E9/F/I/B/UP/S), black
  (line-length 100), mypy (Python 3.12, ignore-missing-imports), pytest (`-q`).
- Package license field updated to PEP 639 string format (`license = "MIT"`).
- All 113 source and test files reformatted with black.
- Ruff auto-fixed 876 issues; 6 resolved manually.

### Fixed

- `config show` crash on scalar top-level fields.
- `safe_parser.py` — `ast.Comparison` → `ast.Compare`, `ast.Comprehension` →
  `ast.comprehension`; removed deprecated `ast.Num` / `ast.Str` / `ast.Index`
  for Python 3.12 compatibility.
- Sandbox subprocess template: `.format()` → `.replace()` to avoid mangling
  dict braces; fixed indentation, `PATH` / `HOME` preservation, `preexec_fn`
  wrapping.
- `CLASSIFICATION_QUALITY` missing `different_style` entry in
  `self_improver.py`.
- `__init__.py` version mismatch (was `0.1.0`).
- Knowledge-graph merge ID collision in `knowledge_graph.py`.
- Duplicate `show_comprehension_gauge` in TUI.
- Stale import paths in test fixtures.

### Security

- All `sympify` paths now route through `safe_parser` AST validation.
- Sandbox subprocess runs with `RLIMIT_AS`, `RLIMIT_CPU`, restricted
  `__builtins__`, and no `shell=True`.
- Journey store validates filenames against path-traversal (`../`, absolute
  paths, null bytes).

## [0.1.0] — 2026-07-01

Initial release.
