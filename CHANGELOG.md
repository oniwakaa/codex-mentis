# Changelog

All notable changes to Pitagora are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
