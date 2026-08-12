# Pitagora — Architecture

## Name
**Pitagora** (Latin: "Book of the Mind") — a CLI for studying, exploring, and reasoning through complex mathematics and physics.

## Design Principles
1. **CLI-native** — beautiful terminal UI, no browser required
2. **Agent-orchestrated** — specialized agents for different tasks
3. **Web-acquired knowledge** — agents discover knowledge from the web, not hardcoded
4. **Source-cited** — every claim traces back to a crawled source
5. **Verification-first** — every mathematical claim can be verified
6. **Self-improving** — the system gets better as you use it
7. **Free to run** — powered by webfetch (zero-cost web search) + local tools

## Tech Stack
- **Language:** Python 3.11+
- **CLI Framework:** Typer + Rich (beautiful terminal output)
- **TUI:** Textual (interactive terminal UI with panels, tables, charts)
- **Math Engine:** SymPy (symbolic), NumPy/SciPy (numerical), Matplotlib (plots)
- **Terminal Plots:** plotext (matplotlib-style plots in terminal)
- **Web Search:** [webfetch](https://github.com/firish/webfetch) (free multi-engine fusion, semantic caching)
- **Memory:** SQLite + vector embeddings
- **Agents:** Multi-provider (OpenAI, Anthropic, Gemini, local via Ollama)
- **Verification:** SymPy sandbox (isolated subprocess)

## Knowledge Acquisition (Key Differentiator)

Instead of hardcoded knowledge, Pitagora **discovers** it:

```
User Query → Intent Classification
        ↓
   webfetch.search()  ← Multi-engine fusion (DDG, Brave, Serper, Tavily)
        ↓                 Zero cost. Semantic caching. 8x fewer tokens.
   webfetch.fetch_url() ← Local extraction (trafilatura, readability)
        ↓
   KnowledgeExtractor  ← Parse equations, definitions, theorems, concepts
        ↓
   KnowledgeBase (SQLite) ← Store with full citations
        ↓
   ConceptGraph.update() ← Build/expand concept DAG dynamically
        ↓
   Agent (Tutor/Prover/etc.) ← Generates cited, grounded response
```

**webfetch** (`pip install webfetch-llm`) replaces all hosted search APIs:
- Works at zero cost out of the box (DDG)
- Multi-engine RRF fusion — add keys for Brave/Serper/Tavily, they join automatically
- Sentence-level compression → 50% fewer tokens at zero recall loss
- Semantic caching with volatility-aware TTLs (prices=15min, specs=90d)
- MCP server built in

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Pitagora CLI / TUI                       │
├──────────┬──────────┬──────────┬──────────┬──────────────────┤
│  Study   │  Explore │  Reason  │  Verify  │  Visualize       │
├──────────┴──────────┴──────────┴──────────┴──────────────────┤
│              Agent Orchestrator (Parallel Workflows)            │
│   Pipeline · Debate · Side-by-Side · Custom Workflows           │
├──────────┬──────────┬──────────┬──────────┬──────────────────┤
│  Tutor   │Researcher│  Prover  │ Reviewer │  Explainer       │
│  Agent   │  Agent   │  Agent   │  Agent   │  Agent           │
├──────────┴──────────┴──────────┴──────────┴──────────────────┤
│              Self-Improver Agent (Thompson Sampling)            │
├──────────┬──────────┬──────────┬──────────┬──────────────────┤
│          │          │  Skills  │  Math    │  Providers       │
│  Memory  │  Concept │  Engine  │  Engine  │  (Multi-LLM)     │
│  System  │  Graph   │ (evolve) │ (SymPy)  │                  │
├──────────┴──────────┴──────────┴──────────┴──────────────────┤
│          Knowledge Acquisition (webfetch pipeline)              │
│   Search → Fetch → Extract → Store → Graph Update               │
├──────────┬──────────┬──────────┬──────────────────────────────┤
│EverMemOS │ Obsidian │  Notion  │  reMarkable │  Web (DDG etc) │
└──────────┴──────────┴──────────┴─────────────┴───────────────┘
```

## Module Structure

```
pitagora/
├── __init__.py
├── __main__.py
├── cli/
│   ├── app.py               # Typer app definition
│   ├── repl.py              # Interactive REPL (Textual TUI or readline)
│   ├── tui.py               # Full Textual TUI application
│   ├── rich_ui.py           # Rich formatting utilities
│   ├── widgets/             # Textual widgets
│   │   ├── concept_graph.py # Interactive concept DAG visualization
│   │   ├── split_reasoning.py # Side-by-side derivation + intuition
│   │   ├── equation_display.py # LaTeX → Unicode rendering
│   │   ├── proof_tree.py    # Interactive proof tree
│   │   ├── plot_widget.py   # Interactive plot with zoom/pan
│   │   ├── agent_panel.py   # Agent status/confidence display
│   │   └── memory_viewer.py # Browse memory layers
│   └── commands/
│       ├── study.py, explore.py, reason.py, verify.py, visualize.py
│       ├── concept.py, memory.py, kb.py, config.py, skills.py
│       └── research.py      # NEW: web research commands
├── agents/
│   ├── base.py              # Base agent (async, tools, streaming)
│   ├── orchestrator.py      # Multi-agent workflow orchestrator
│   ├── tutor.py             # Socratic teaching agent
│   ├── researcher.py        # Deep-dive research (uses webfetch!)
│   ├── prover.py            # Formal derivation + SymPy verification
│   ├── reviewer.py          # Adversarial review + counterexample search
│   ├── explainer.py         # Multi-level explanations (Feynman technique)
│   ├── self_improver.py     # Tracks outcomes, evolves strategies
│   ├── visualizer.py        # Plots, concept maps, proof trees
│   └── providers/
│       ├── base.py          # Provider interface
│       ├── openai.py, anthropic.py, gemini.py, local.py
│       └── __init__.py      # Provider factory + fallback chains
├── core/
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic data models
│   └── constants.py
├── memory/
│   ├── store.py             # SQLite memory store
│   ├── layers.py            # 3-layer memory (L1 session, L2 topic, L3 synthesis)
│   ├── retrieval.py         # Semantic + hybrid search
│   └── spaced_repetition.py # SM-2 algorithm
├── concepts/
│   ├── graph.py             # Dynamic concept DAG (grows from research!)
│   ├── tracker.py           # Mastery tracking per concept
│   └── curriculum.py        # Adaptive learning path generation
├── knowledge/               # ← THE KEY DIFFERENTIATOR
│   ├── acquisition.py       # Research pipeline: search → fetch → extract → store
│   ├── webfetch_bridge.py   # webfetch integration (free multi-engine search)
│   ├── extractor.py         # Parse equations/definitions/theorems from text
│   ├── base.py              # Knowledge base (SQLite + search)
│   ├── chunker.py           # Smart chunking for math content
│   └── embeddings.py        # Embedding generation (sentence-transformers or TF-IDF)
├── math_engine/
│   ├── sandbox.py           # SymPy sandbox (isolated subprocess)
│   ├── symbolic.py          # Symbolic computation helpers
│   ├── numerical.py         # Numerical computation helpers
│   ├── verification.py      # Multi-level verification
│   ├── plots.py             # Terminal + file plots
│   └── latex_render.py      # LaTeX to terminal rendering
├── skills/
│   ├── engine.py            # Skills management
│   ├── evolution.py         # Self-improving skills (Thompson Sampling)
│   └── builtin/*.yaml       # Seed skills for math/physics domains
├── mcp_integration/
│   ├── client.py            # MCP client wrapper
│   ├── evermemos.py         # EverMemOS persistent memory
│   ├── obsidian.py          # Obsidian vault integration
│   └── remarkable.py        # reMarkable tablet integration
└── data/
    └── concepts.yaml        # Seed concept graph (dynamically expanded)
```

## Core Concepts

### 1. Knowledge Acquisition (NEW — replaces hardcoded KB)
The agent researches topics by:
1. Searching with webfetch (DDG + any keys you add, fused via RRF)
2. Fetching pages locally (no API cost for content extraction)
3. Extracting equations, definitions, theorems via regex heuristics
4. Storing in SQLite with full citations (URL, title, date)
5. Expanding the concept graph with discovered relationships

### 2. Modes
- **Study** — structured learning with spaced repetition, concept progression
- **Explore** — free-form investigation, "what if" scenarios
- **Reason** — formal derivations with Generate-Verify-Revise
- **Verify** — adversarial review of claims and proofs
- **Visualize** — terminal plots, concept maps, proof trees
- **Research** — web-acquired deep dives with citations

### 3. Agents
Each agent is a specialized LLM call with:
- Fresh context (no pollution between roles)
- Role-specific system prompt
- Tool access (SymPy, webfetch search, KB retrieval)
- Structured output format
- **Orchestrator** routes to the right agent, supports parallel workflows

### 4. Memory (3-layer)
- **L1 (Session)** — current conversation trace, ephemeral
- **L2 (Topic)** — per-topic knowledge, persists across sessions
- **L3 (Synthesis)** — cross-topic insights, long-term memory
- Plus: Concept Graph with mastery scores, Spaced Repetition (SM-2)

### 5. Self-Improvement
- Tracks which explanations lead to correct answers
- Thompson Sampling for strategy selection
- Evolves prompts based on success metrics
- Generates new skills from successful patterns

## Configuration

```yaml
# ~/.pitagora/config.yaml
providers:
  default: gemini
  reasoning: openai
  vision: anthropic
  local: ollama

memory:
  backend: sqlite
  vector_model: all-MiniLM-L6-v2
  spaced_repetition: true

knowledge:
  search_engine: webfetch  # Uses webfetch's multi-engine fusion
  max_sources_per_topic: 5
  auto_research: true       # Auto-research when agent lacks knowledge

math:
  sandbox: sympy
  verification_levels: [computational, cross_check]
  plot_backend: plotext

ui:
  theme: dark
  latex: true
  plots: terminal
```

## Installation

```bash
pip install pitagora[all]
# or minimal (no embeddings, no MCP):
pip install pitagora
```

## Usage

```bash
pitagora                              # Launch TUI
pitagora study "Lagrangian mechanics" # Socratic study session
pitagora explore "What if gravity 2x?"
pitagora derive "Euler-Lagrange from least action"
pitagora verify "Hermitian eigenvalues are real"
pitagora research "topological insulators" --depth deep  # Web research!
pitagora plot "sin(x) * e^(-x)" --range 0 10
pitagora concept map "quantum mechanics"
```
