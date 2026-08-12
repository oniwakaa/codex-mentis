# Pitagora — Deep Codebase Audit

Clone `https://github.com/oniwakaa/codex-mentis.git` and work locally.

Read the entire codebase systematically. Every .py file under `codex_mentis/`, every .yaml under `data/`, `pyproject.toml`, and the test files. Then produce a comprehensive audit report and fix everything.

---

## What to Look For

### 1. Bugs & Broken Logic

- Anything that would crash at runtime — missing imports, wrong function signatures, referencing attributes/keys that don't exist
- Logic errors — conditions that can never be true, off-by-one, unreachable code paths
- Race conditions or resource leaks (unclosed DB connections, file handles)
- Error handling that silently swallows exceptions and hides real problems (bare `except: pass` everywhere)
- Type mismatches — passing wrong types between modules, especially between the YAML workflow engine and the agent classes
- Config loading failures — what happens if `~/.pitagora/` doesn't exist yet? If config.yaml is malformed? If a provider is unreachable?

### 2. Dead Code & Empty Stubs

- Functions, classes, or entire modules that are never called from anywhere
- Empty `__init__.py` files that could at least export key classes
- Agent classes (prover, debate, researcher, reviewer, visualizer, chain_of_thought) — check if they're actually instantiated and used anywhere, or if they're dead code sitting next to the chat REPL that bypasses them
- The orchestrator and workflow engine — are they wired into the user-facing CLI or do they just exist as code nobody calls?
- The MCP integration module — empty or functional?
- The TUI widgets module — empty or functional?
- Import statements that import things never used in that file

### 3. God Objects & Single Responsibility Violations

- `chat.py` — this is likely a god file. It probably handles UI, config loading, provider communication, RAG, concept graph queries, user graph queries, memory persistence, math verification, session management, and the REPL loop all in one file. Identify what should be extracted.
- `orchestrator.py` — does it try to do too much?
- Any file over 300 lines that does multiple unrelated things
- Classes with more than 10 methods that aren't cohesive
- Functions over 50 lines that should be broken down

### 4. Prompt Engineering Audit

Read every system prompt, agent prompt template, and workflow YAML prompt. For each one:

- **Is it over-specified?** Does it tell the LLM things it already knows? Remove redundant instructions. The principle: if removing a sentence doesn't change the output, remove it.
- **Is it under-specified?** Are there ambiguous instructions where the LLM might go wrong? Add guardrails only where needed.
- **Does it use positive framing?** "Do X" is better than "Don't do Y." Convert negative instructions to positive ones where possible.
- **Is it too long?** Long prompts waste tokens and dilute focus. Can the same instruction be said in fewer words?
- **Does it specify output format clearly?** If the code parses the LLM's output, the prompt must specify the exact format. If the output is just displayed, format constraints are unnecessary overhead.
- **Are there conflicting instructions?** One part says "be concise" while another says "be thorough."

Key files to audit for prompts:
- `chat.py` — the main system prompt
- `agents/explainer.py`, `tutor.py`, `prover.py`, etc. — each agent's system prompt
- `data/workflows/*.yaml` — all workflow prompt templates
- `skills/builtin/*.yaml` — skill prompts
- Any other file that constructs LLM messages

Apply the **minimal prompting principle**: every word in a prompt should earn its place. If the LLM would do the same thing without an instruction, that instruction is waste.

### 5. Missing Error Paths

- What happens when the LLM returns garbage or times out?
- What happens when SymPy can't parse an equation?
- What happens when the concept graph doesn't contain the requested topic?
- What happens when the knowledge base is empty?
- What happens when config.yaml doesn't exist (first run)?
- What happens when the user sends empty input, very long input, or non-ASCII input?

### 6. Architecture Opportunities

- Is there a clear separation between data layer, business logic, and presentation?
- Could the agent system benefit from a proper message bus or event system instead of direct function calls?
- Is the YAML workflow engine actually flexible enough, or is it too rigid/too loose?
- Are there circular import risks?
- Is there proper dependency injection or is everything hardcoded?
- Could any of the current code be replaced by well-maintained libraries?
- Is the test suite actually testing behavior or just smoke-testing imports?

### 7. Consistency Issues

- Naming conventions — are they consistent across files? (snake_case vs camelCase, naming patterns)
- Error message formatting — consistent style?
- Config key naming — consistent conventions?
- Docstrings — present where needed? Accurate?
- Type hints — used consistently? Correct?

---

## Deliverables

### First: Audit Report

Create `AUDIT_REPORT.md` in the repo root with:
- **Critical bugs** — things that would crash or produce wrong results
- **Dead code** — files/functions/classes that can be removed or are unused stubs
- **God objects** — files that need to be split, with suggested decomposition
- **Prompt audit** — for each prompt: location, current length, issues found, suggested minimal version
- **Missing error handling** — with suggested fixes
- **Architecture issues** — structural problems and suggested improvements
- **Consistency issues** — naming, formatting, style inconsistencies

### Second: Fix Everything

After the audit report, fix all identified issues:
- Fix critical bugs
- Remove or properly stub dead code
- Split god objects into focused modules
- Rewrite prompts to be minimal and effective
- Add missing error handling
- Fix consistency issues

Run `python -m pytest tests/ -x` after fixes. Add new tests for any bugs you fixed. Commit the audit report and fixes separately.

---

## Guidelines

- Don't break existing functionality — every fix should be backwards-compatible
- Don't add new dependencies
- When splitting a god object, keep the public API the same (import paths can change if doing the Task 1 rename, but function signatures should stay compatible)
- When simplifying prompts, verify the simplified version still produces good output — if unsure, keep the original but mark it as "consider simplifying"
- Be thorough — read every file, not just the obvious ones
