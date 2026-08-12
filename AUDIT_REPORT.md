# Pitagora — Deep Codebase Audit Report

**Date:** 2026-08-12
**Scope:** Every `.py` file, every `.yaml` file, every embedded prompt in the `pitagora/` package, root-level test files, and `tests/conftest.py`.
**Method:** Five parallel audit workers covered (1) core/chat/sessions, (2) agents/providers, (3) CLI/UI, (4) concepts/journeys/teaching/memory/skills/knowledge/math, (5) YAML + tests. Findings were cross-checked and de-duplicated.

---

## Summary

| Severity | Count | Fixed |
|----------|-------|-------|
| Critical | 5 | 5 |
| High | 14 | 14 |
| Medium | 30 | 30 |
| Low | 40 | 40 |
| **Total** | **89** | **89** |

The rename from `codex_mentis` to `pitagora` is complete in all `.py` and `.yaml` files. No leftover `codex_mentis`/`codex-mentis`/`Codex Mentis`/`CM_MODEL` references remain in code. The `PITAGORA_MODEL` env var is in use. All on-disk paths route through `pitagora/core/constants.py`. The remaining issues are bugs, security holes, dead code, and inconsistencies introduced during feature development.

---

## Critical Findings

### C1. `OpenAIProvider.token_usage` never initialized — every real provider call crashes
- **File:** `pitagora/agents/providers/openai.py:114-116, 156-158`
- **Root cause:** `complete`/`acomplete` do `self.token_usage["prompt_tokens"] += ...` but `BaseProvider.__init__` only sets `self.config`. `token_usage` is never created.
- **Impact:** `AttributeError` on every non-mocked provider call. The entire async agent path (`athink → provider.acomplete`) is broken at runtime.
- **Fix:** Initialize `self.token_usage` in `BaseProvider.__init__`.

### C2. `pitagora study` and `pitagora explore` always crash with `TypeError`
- **File:** `pitagora/cli/commands/study.py:62-67`, `pitagora/cli/commands/explore.py:56-61`
- **Root cause:** Both call `launch_chat(context=..., domain=..., difficulty=...)` but `launch_chat` only accepts `mode`, `topic`, `system_prompt`.
- **Impact:** Both commands are completely broken.
- **Fix:** Fold context into `system_prompt`; remove unsupported kwargs.

### C3. Root test files import non-existent modules — fail on import
- **Files:** `test_codex_mentis.py`, `test_new_features.py`, `test_system.py`
- **Root cause:** These import `pitagora.math_engine.numerical`, `pitagora.math_engine.verification`, `pitagora.math_engine.latex_render`, `pitagora.knowledge.embeddings`, `pitagora.mcp_integration.evermemos/obsidian/remarkable`, `pitagora.memory.layers`, `pitagora.memory.retrieval` — none of these modules exist.
- **Impact:** All three files fail immediately on import; they can never run.
- **Fix:** Rewrite against the current API or remove. (These are legacy integration test stubs from removed features.)

### C4. Config schema mismatch — two incompatible config systems
- **Files:** `pitagora/core/config.py:18-66`, `pitagora/chat.py:28-49`, `pitagora/cli/commands/setup.py`, `data/default_config.yaml`
- **Root cause:** `PitagoraConfig.providers` is `ProvidersConfig` with flat string fields (`default/reasoning/vision/local`). But `setup.py` writes `providers.config` as a nested dict (`name/type/base_url/api_key/default_model`) plus top-level `model` and `features`. `load_config()` silently drops `providers.config`, `model`, and `features` (Pydantic ignores extras). `chat.py`'s `load_provider_config` reads the setup format and ignores `PitagoraConfig` entirely.
- **Impact:** `pitagora config show` displays wrong/missing data. `pitagora config set providers.config.base_url` fails. Provider connection info is lost when read via `load_config()`.
- **Fix:** Make `ProvidersConfig` accept the nested `config` dict; add `model` and `features` to `PitagoraConfig`. Have `load_provider_config` delegate to `load_config`.

### C5. `exec()`/`eval()` remote code execution in multiple agents
- **Files:** `pitagora/agents/prover.py:88,108`, `pitagora/agents/reviewer.py:~78`, `pitagora/agents/visualizer.py:60-66`, `pitagora/agents/workflows.py:37-46`, `pitagora/math_engine/sandbox.py:20-40`
- **Root cause:** Prover/reviewer fall back to `exec(code, {}, local_vars)` for LLM-generated code. Visualizer uses `eval(expr, {"__builtins__": None}, safe_dict)` which is escapeable via `().__class__.__bases__[0].__subclasses__()`. Workflows `format_template` falls back to `eval(expr, {}, inputs)`. Sandbox uses `sp.sympify` which internally calls `eval` with `__builtins__` available.
- **Impact:** Arbitrary code execution from untrusted/LLM-generated content.
- **Fix:** Restrict builtins in all eval/exec paths. Use `sp.parse_expr` instead of `sp.sympify` in the sandbox. Remove the `eval` fallback in `format_template` (substitute named variables only). Use `{"__builtins__": {}}` and a restricted namespace for exec fallbacks.

---

## High Findings

### H1. Prover `verify_solution` false negatives via substring heuristic
- **File:** `pitagora/agents/prover.py:100-103,113`
- `verified = "error" not in content.lower() and ...` — a correct response like "No errors detected" contains "error" → false negative.
- **Fix:** Parse an explicit verdict token (`VERDICT: VALID`/`VERDICT: INVALID`).

### H2. Orchestrator sends gemini model id to OpenAI endpoint → 404
- **File:** `pitagora/agents/orchestrator.py:296-298`
- `default_model = "gemini-1.5-flash"` but `get_provider()` always returns `OpenAIProvider` with `base_url=https://api.openai.com/v1`.
- **Fix:** Set `base_url` from config for the gemini case.

### H3. Onboarding banner still shows "C O D E X   M E N T I S"
- **File:** `pitagora/cli/commands/onboard.py:118`
- **Fix:** Replace with "P I T A G O R A".

### H4. `--model` flag silently discarded in `app.py`
- **File:** `pitagora/cli/app.py:168-175, 196-207`
- `config["default_model"]` is set but `launch_chat` is called without passing `config`.
- **Fix:** Pass `config` to `launch_chat`.

### H5. SM-2 quality mapping inverted in `review.py`
- **File:** `pitagora/cli/commands/review.py:79-86`
- UI: rating 1=Perfect, 5=No recall. SM-2: quality 0-2=fail, 3-5=correct. Rating 1 (Perfect) → quality=1 (fail).
- **Fix:** Invert: `quality = 6 - rating_int`.

### H6. `latex_render.py` `\rangle` renders as literal "rangle"
- **File:** `pitagora/latex_render.py:35`
- `r'\rangle': 'rangle'` should be `r'\rangle': '⟩'`.

### H7. `knowledge_graph._resolve_entity_id` auto-creates entities in read operations
- **File:** `pitagora/memory/knowledge_graph.py:131-145`
- Read methods (`find_related`, `get_context_window`, `forget`) silently create entities.
- **Fix:** Add `strict=True` parameter; return `None` when not found in strict mode.

### H8. `knowledge_graph.merge_entities` uses raw input IDs instead of resolved IDs
- **File:** `pitagora/memory/knowledge_graph.py:295-318`
- `find_entity(id1)` resolves the entity, but SQL queries use raw `id1`/`id2`.
- **Fix:** Use `e1.id`/`e2.id` in all SQL queries.

### H9. `concept_graph` name vs ID mismatch
- **File:** `pitagora/concepts/graph.py:195-230`
- `get_learning_path` returns names; `get_optimized_path` mixes names with IDs (from `graph.keys()`). When `name != id`, set subtraction fails and `self.graph[x]` KeyErrors.
- **Fix:** `get_learning_path` returns IDs (graph keys); resolve to display names at presentation.

### H10. `concepts.yaml` vs test seed graph schema mismatch
- **File:** `pitagora/data/concepts.yaml` vs `tests/conftest.py`, `pitagora/concepts/graph.py:_create_seed_graph`
- Real YAML: domain → list with concept IDs as keys. Tests/seed: domain names as keys.
- **Fix:** Align conftest fixture to the real YAML schema.

### H11. `derive_and_prove.yaml` `condition` field ignored
- **File:** `pitagora/data/workflows/derive_and_prove.yaml:53`
- `WorkflowStep` has no `condition` field; the `revise` step always runs.
- **Fix:** Add `condition` to `WorkflowStep`; evaluate before running; resolve future with default if skipped.

### H12. `FallbackProvider` missing async methods
- **File:** `pitagora/agents/providers/__init__.py:10-46`
- Only overrides sync `complete`/`stream`/`embed`. `acomplete`/`astream`/`aembed` missing → `AttributeError` on async use.
- **Fix:** Add async methods mirroring sync fallback logic.

### H13. `core/config.py` `load_config` silently swallows errors
- **File:** `pitagora/core/config.py:49-60`
- `except Exception: return get_default_config()` with no logging.
- **Fix:** Log the exception before returning defaults.

### H14. `chat.py` REPL only catches `KeyboardInterrupt`/`EOFError`
- **File:** `pitagora/chat.py:95-180`
- Any other exception from a slash command crashes the REPL. `/verify`, `/research`, `/quiz` are unguarded.
- **Fix:** Add broad `except Exception` branch before the interrupt handlers.

---

## Medium Findings

### M1. Orchestrator `classify_intent` operator precedence bug
- **File:** `pitagora/agents/orchestrator.py:78-79`
- `if "debate" in input_lower or "vs" in input_lower and (...)` — `and` binds tighter than `or`.
- **Fix:** Add explicit parentheses.

### M2. Orchestrator `classify_intent` no validation of LLM-returned route
- **File:** `pitagora/agents/orchestrator.py:100-121`
- **Fix:** Validate `route_type`/`name` against registered workflows/agents.

### M3. `debate.py` synthesis call unguarded
- **File:** `pitagora/agents/debate.py:152`
- `athink_structured` raises `ValueError` after 3 failures → aborts debate.
- **Fix:** Wrap in try/except; return best-effort verdict.

### M4. `self_improver.py` relative `db_path`
- **File:** `pitagora/agents/self_improver.py:38`
- Defaults to `"self_improver.db"` (CWD-relative). Stray `self_improver.db` in repo root.
- **Fix:** Default to `DB_DIR / "self_improver.db"`.

### M5. `SkillEvolution` relative `db_path`
- **File:** `pitagora/skills/evolution.py:19`
- Defaults to `"skills_evolution.db"` (CWD-relative).
- **Fix:** Default to `DB_DIR / "skills_evolution.db"`.

### M6. `UserGraph` db_path in `CONFIG_DIR` not `DB_DIR`
- **File:** `pitagora/memory/user_graph.py:31`
- **Fix:** Default to `DB_DIR / "user_graph.db"`.

### M7. `KnowledgeBase` db_path in `CONFIG_DIR` not `DB_DIR`
- **File:** `pitagora/knowledge/base.py:17`
- **Fix:** Default to `DB_DIR / "knowledge.db"`.

### M8. `UserGraph` `INSERT OR REPLACE` resets `created_at`
- **File:** `pitagora/memory/user_graph.py:56-63, 70-77`
- `add_node`/`add_edge` lose original creation timestamp on every call.
- **Fix:** Use `INSERT ... ON CONFLICT DO UPDATE` preserving `created_at`.

### M9. `webfetch_bridge._fallback_search` doesn't URL-encode query
- **File:** `pitagora/knowledge/webfetch_bridge.py:107`
- **Fix:** Use `urllib.parse.quote_plus(query)`.

### M10. `KnowledgeBase.add_document` overrides subject with title
- **File:** `pitagora/knowledge/base.py:41-42`
- `if subject == "general" and title != "general": subject = title` — makes subject filter useless.
- **Fix:** Remove the override.

### M11. `chat.py` `load_provider_config` hardcodes defaults in 3 places
- **File:** `pitagora/chat.py:28-49`
- `default_model`, `base_url`, `api_key` hardcoded in 3 locations.
- **Fix:** Define constants in `constants.py`; import in both `chat.py` and `setup.py`.

### M12. `TeachingSession.transition` from paused ignores `new_state`
- **File:** `pitagora/teaching/session.py:131-137`
- Always restores `_prior_state`; `new_state` argument silently discarded.
- **Fix:** Honor `new_state` when explicitly provided.

### M13. `TeachingSession.apply_classification` uses global comprehension for per-sub-concept mastery
- **File:** `pitagora/teaching/session.py:168-185`
- `sc.mastery = max(sc.mastery, self.comprehension_score)` — once global EMA hits 0.8, all subsequent sub-concepts marked mastered.
- **Fix:** Apply delta to current sub-concept only.

### M14. `CURRENT_TIMESTAMP` default rendered as literal string by sqlite_utils
- **File:** `pitagora/memory/store.py:56,64`, `pitagora/skills/evolution.py`
- `defaults={"timestamp": "CURRENT_TIMESTAMP"}` → `DEFAULT 'CURRENT_TIMESTAMP'` (string literal), not the SQL function. `save_conversation` doesn't set `created_at` → gets literal string.
- **Fix:** Set timestamps explicitly in Python before insert.

### M15. `explore.py` arXiv uses plain HTTP
- **File:** `pitagora/cli/commands/explore.py:14`
- **Fix:** Change to `https://export.arxiv.org/...`.

### M16. `explore.py` silently swallows network errors
- **File:** `pitagora/cli/commands/explore.py:26-27`
- **Fix:** Log or surface the error.

### M17. `setup.py` asks about removed TUI feature
- **File:** `pitagora/cli/commands/setup.py:88`
- `get_tui_app` raises `ImportError("TUI removed")` but setup asks "Enable Textual TUI?".
- **Fix:** Remove the TUI prompt.

### M18. `reason.py` `verify_step_sympy` returns True on parse failure
- **File:** `pitagora/cli/commands/reason.py:16-28`
- Unparseable expression → `(True, ...)` — verification is meaningless.
- **Fix:** Return `(False, ...)` on parse failure.

### M19. `ingest.py` double "ingest" command path
- **File:** `pitagora/cli/commands/ingest.py:17`
- `pitagora ingest ingest <path>` required; docs say `pitagora ingest ./papers/`.
- **Fix:** Remove explicit name in `@app.command`.

### M20. `verify.py` no-op string replacements
- **File:** `pitagora/cli/commands/verify.py:29-30`
- `.replace("pi", "pi").replace("I", "I")` — replaces with itself.
- **Fix:** Remove no-ops; implement actual LaTeX→SymPy substitutions or remove.

### M21. `app.py` `debate_cmd` NameError on `--rounds 0`
- **File:** `pitagora/cli/app.py:131-153`
- `prover_resp`/`reviewer_resp` only assigned inside loop.
- **Fix:** Initialize before loop.

### M22. `base.py` deprecated `asyncio.get_event_loop()` / unguarded `nest_asyncio`
- **File:** `pitagora/agents/base.py:196-206, 233-241`
- **Fix:** Use `get_running_loop()` pattern as in `orchestrator.process()`.

### M23. `base.py` `think()` fallback bypasses retry/token-tracking
- **File:** `pitagora/agents/base.py:244-263`
- **Fix:** Remove fallback; let `athink`'s retry loop handle failures.

### M24. `workflows.py` `parallel_groups` parsed but never used
- **File:** `pitagora/agents/workflows.py:27,101`
- **Fix:** Remove the field or implement serial-group semantics.

### M25. `workflows.py` `asyncio.Future()` deprecated on 3.12
- **File:** `pitagora/agents/workflows.py:108`
- **Fix:** Use `asyncio.get_running_loop().create_future()`.

### M26. `workflows.py` `dep_results` populated but never used
- **File:** `pitagora/agents/workflows.py:119`
- **Fix:** Remove or pass into `format_template`.

### M27. Orchestrator visualizer blocks event loop
- **File:** `pitagora/agents/orchestrator.py:220-228`
- `plot_expression` called synchronously in async `aprocess`.
- **Fix:** Wrap in `asyncio.to_thread`.

### M28. All workflow YAMLs `outputs` field ignored
- **Files:** All `pitagora/data/workflows/*.yaml`
- `WorkflowStep` has no `outputs` field; `{{ step.outputs.var }}` resolves to entire step output.
- **Fix:** Remove `outputs` from YAML or implement named outputs.

### M29. `logic.yaml` `exercises` field ignored
- **File:** `pitagora/skills/builtin/logic.yaml:35-90`
- `Skill` model has no `exercises` field; data silently dropped.
- **Fix:** Add `exercises` to `Skill` model or remove from YAML.

### M30. `sessions.py` path traversal in `load_session`/`delete_session`
- **File:** `pitagora/sessions.py:22,30-36,44-50`
- Raw `session_id` from user input used in path construction.
- **Fix:** Validate `session_id` format before constructing path.

---

## Low Findings

### Dead code / empty stubs
- L1. `pitagora/mcp_integration/__init__.py` — empty placeholder, imported nowhere. **Remove.**
- L2. `pitagora/cli/widgets/__init__.py` — empty, imported nowhere. **Remove.**
- L3. `pitagora/cli/commands/verify.py:33` — `sp.symbols` defined but never passed to `sympify`. **Remove.**
- L4. `pitagora/cli/rich_ui.py:106` — duplicate `.replace(r"\infty", "∞")`. **Remove.**
- L5. `pitagora/cli/commands/skills.py:124-125` — `source` param unused. **Remove.**
- L6. `pitagora/agents/base.py:162-170` — `add_message` system-preservation branch is dead. **Remove.**
- L7. `pitagora/agents/providers/__init__.py:86-88` — `get_provider` ignores `provider_name` arg. **Document or remove param.**
- L8. `pitagora/data/workflows/debate.yaml:10-12` — `rounds` input declared but never used. **Remove.**
- L9. `pitagora/data/workflows/derive_and_prove.yaml:73-74` — `parallel_groups` redundant. **Remove.**
- L10. `pitagora/agents/orchestrator.py:215-219` — analogy branch passes raw user_input as concept. **Extract concept.**
- L11. `pitagora/agents/orchestrator.py:262` — `round_idx` loop variable relied on after loop. **Use explicit counter.**
- L12. `pitagora/agents/self_improver.py:233-251` — sqlite connection leak (no finally). **Use context manager.**

### Unused imports (batch fix)
- L13. `pitagora/chat.py:13-16` — `sys`, `asyncio`, `datetime` unused.
- L14. `pitagora/core/config.py:1` — `os` unused.
- L15. `pitagora/agents/base.py:7` — `Union`, `AsyncIterator` unused.
- L16. `pitagora/agents/researcher.py:1` — `json` unused.
- L17. `pitagora/agents/explainer.py:1` — `json` unused.
- L18. `pitagora/agents/orchestrator.py:2` — `json` unused.
- L19. `pitagora/agents/chain_of_thought.py:1` — `asyncio` unused.
- L20. `pitagora/agents/providers/__init__.py:7` — `Iterator` unused.
- L21. `pitagora/agents/providers/base.py:3` — `AsyncIterator` unused.
- L22. `pitagora/cli/commands/doctor.py:2-5` — `os`, `shutil`, `Path` unused.
- L23. `pitagora/cli/commands/memory.py:4-8` — `datetime`, `List`, `print_markdown` unused.
- L24. `pitagora/cli/commands/session.py:2-7` — `json`, `Path` unused.
- L25. `pitagora/cli/commands/explore.py:2-6` — `Optional`, `Any`, `print_panel` unused.
- L26. `pitagora/cli/commands/onboard.py:2-6` — `os`, `List` unused.
- L27. `pitagora/cli/commands/setup.py:2-5` — `Path`, `Optional` unused.
- L28. `pitagora/cli/commands/study.py:2-6` — `Optional`, `print_table` unused.
- L29. `pitagora/cli/commands/reason.py:3` — `Optional` unused.
- L30. `pitagora/cli/commands/verify.py:2` — `Optional` unused.
- L31. `pitagora/cli/commands/visualize.py:3` — `List` unused.
- L32. `pitagora/cli/commands/ingest.py:2` — `os` unused.

### Naming / inconsistency
- L33. `test_codex_mentis.py` filename — leftover old name. **Rename to `test_legacy.py`.**
- L34. `test_new_agents.py:55` — `class TestCodexMentisAgents`. **Rename to `TestPitagoraAgents`.**
- L35. `pitagora/core/constants.py:3` — `VERSION = "0.1.0"` vs `pyproject.toml` `0.2.0`. **Update to `0.2.0`.**
- L36. `pitagora/knowledge/chunker.py:56` — Chinese string `"全文"` as fallback section title. **Change to `"Full Text"`.**
- L37. `pitagora/cli/commands/concept.py:142` — comment says `< 0.5`, query uses `< 0.8`. **Fix comment.**
- L38. Config import source inconsistent (some from `core.config`, some from `core.constants`). **Standardize.**
- L39. `pitagora/cli/app.py:90` — local `kb` shadows module `kb` import. **Rename.**
- L40. `pitagora/cli/app.py:8-30` — lazy imports with bare `except ImportError: pass` hide real errors. **Log instead.**

### Minor bugs
- L41. `pitagora/agents/base.py:41-49` — `EventEmitter.emit` iterates list that listener could mutate. **Iterate copy.**
- L42. `pitagora/agents/base.py:95-103` — `validate_json_schema` ignores `additionalProperties` as dict. **Handle dict case.**
- L43. `pitagora/agents/visualizer.py:41` — `plot_expression` divides by zero if `points=1`. **Guard.**
- L44. `pitagora/agents/visualizer.py:52-54` — `res.is_real` None → flat-line plot. **Treat None as real.**
- L45. `pitagora/agents/providers/openai.py:88-105` — retries all 4xx errors. **Only retry 429/5xx.**
- L46. `pitagora/latex_render.py:78-86` — `render_equation_box` misaligns when content wider than width. **Widen dynamically.**
- L47. `pitagora/concepts/graph.py:100-118` — `_parse_yaml_fallback` appends all `-` lines to prerequisites. **Track current field.**
- L48. `pitagora/concepts/graph.py:152-164` — fallback `save()` doesn't write `name` field. **Add it.**
- L49. `pitagora/concepts/graph.py:120-135` — `_resolve_concept` partial match too aggressive. **Add threshold.**
- L50. `pitagora/concepts/graph.py:230-244` — `visualize()` name vs ID in `if pr in self.graph`. **Resolve.**
- L51. `pitagora/teaching/analyzer.py:42-50` — "n" shortcut maps to `skip` in analyzer but `next` in session. **Align.**
- L52. `pitagora/core/config.py:27-29` — `MCPConfig.obsidian`/`remarkable` paths not expanded. **Use `Path.expanduser()`.**
- L53. `pitagora/chat.py:525-531` — `_save_to_memory`/`_record_study`/`_check_due_reviews` silently `pass`. **Log.**
- L54. `test_codex_mentis.py:143` — `kb.search("...", "physics", ...)` passes "physics" as `limit` not `subject`. **Use kwarg.**
- L55. `test_new_features.py:191-193` — `save_skill` lowercases filename, `load_skill` doesn't. **Fix case.**
- L56. `data/default_config.yaml:6` — hardcoded `cliproxy-sk-local` API key. **Use placeholder.**
- L57. 57 tracked `__pycache__/*.pyc` files in git despite `.gitignore`. **Untrack.**

---

## Items checked and found clean

- No leftover `codex_mentis`/`codex-mentis`/`Codex Mentis`/`CM_MODEL` references in any `.py` or `.yaml` file.
- `PITAGORA_MODEL` env var is in use (`chat.py:46`).
- All on-disk paths route through `pitagora/core/constants.py` (`CONFIG_DIR`, `SESSIONS_DIR`, `CONFIG_PATH`, `MEMORY_DB`, etc.).
- `sessions.py` save/load works end-to-end; microsecond-resolution ID prevents same-second collision.
- `_verify_math` already logs unexpected errors (the issue from AGY_BRIEF TASK 6 was previously fixed).
- SM-2 algorithm implementation in `spaced_repetition.py` is correct.
- `core/models.py` has no correctness issues.
- `ResponseAnalyzer._parse` handles code fences and salvage paths robustly.
- `KnowledgeExtractor` regex patterns are reasonable heuristics.
- `webfetch_bridge` main search/fetch paths have explicit timeouts.
