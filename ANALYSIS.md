# Deep Analysis: Existing Math/Physics CLI Tools

## 1. DeepTutor (HKUDS)
**Repo:** github.com/HKUDS/DeepTutor

### Strengths
- CLI-native with full REPL (`deeptutor chat`)
- 3-layer memory (L1 traces, L2 summaries, L3 synthesis) — inspectable and editable
- Knowledge Base system with RAG (LlamaIndex, GraphRAG, LightRAG, Obsidian vaults)
- Multiple capabilities: chat, deep_solve, deep_question, deep_research, visualize, math_animator, mastery_path
- Agent-native: `--format json` for machine consumption, SKILL.md for agent handoff
- Skills ecosystem (EduHub) — community-installable extensions
- Partners system — persistent AI companions with personality
- Notebook system for structured learning
- Supports multiple LLM providers

### Weaknesses
- No MCP integration (custom plugin system instead)
- Memory is inspectable but not truly adaptive — no spaced repetition or learning curves
- Visualization is web-dependent (charts/animations in browser)
- No proof verification (no Lean/Coq integration)
- No SymPy/NumPy sandbox for computational verification
- The "mastery path" is linear, not graph-based
- No reMarkable/tablet integration
- Heavy dependencies (FastAPI backend, Node.js frontend for full install)

### Key Takeaway
Best overall architecture. The 3-layer memory + KB + capabilities model is the right foundation.

---

## 2. Alethic (hyperion-git)
**Repo:** github.com/hyperion-git/alethic

### Strengths
- Generate-Verify-Revise loop — decoupled verification (inspired by DeepMind's Aletheia)
- SymPy + NumPy sandbox with process-level isolation
- Physics-specific: dimensional analysis, limiting cases, Lagrangian mechanics
- Scientific figure generation with publication quality
- Tool guidance system (switchable SymPy/NumPy overlays)
- False-premise detection and strategic failure admission
- Works as Claude Code skill or standalone Python library

### Weaknesses
- Tightly coupled to Claude (Opus specifically) — no multi-model support
- No persistent memory across sessions
- No knowledge base or RAG
- No interactive REPL — batch mode only
- No learning progression or spaced repetition
- Skills are static prompt templates, not evolving
- No MCP integration
- No visualization beyond static matplotlib figures

### Key Takeaway
The Generate-Verify-Revise loop is the gold standard for mathematical rigor. The sandbox model should be adopted.

---

## 3. PhysicsIntern (HuggingFace)
**Repo:** github.com/huggingface/physics-intern

### Strengths
- 9 specialized agent roles (surveyor, planner, researcher, computer, reviewer, deep critic, adjudicator, formatter)
- Multi-agent pipeline with role specialization
- Git-versioned workspace — every step recoverable
- Fresh context per agent call (no context pollution)
- Host-agnostic (Claude Code, Pi, Codex, OpenCode)
- `research_log.md` as durable state — session-independent
- Problem YAML format for reproducible research
- `/autoresearch` mode for fully autonomous operation

### Weaknesses
- Designed for one-shot research problems, not continuous learning
- No memory persistence between research sessions
- No knowledge base or RAG
- No interactive exploration — fire and forget
- No proof verification
- No visualization
- Heavy workspace scaffolding (many files per problem)
- No MCP integration
- No adaptive difficulty

### Key Takeaway
The multi-agent role system is excellent. The research methodology (survey → plan → derive → compute → review → critique → finalize) is a great learning arc.

---

## 4. AlgeBench (ibenian)
**Repo:** github.com/ibenian/algebench

### Strengths
- 3D interactive visualization with live AI narrator
- Semantic graph: expression → D3 flowchart (see structure, not just symbols)
- Proof animations with step-by-step derivation morphing
- Interactive parameter manipulation (sliders, real-time updates)
- TTS integration (narrated explanations)
- Scene-based learning (modular lesson system)

### Weaknesses
- Web-based (not CLI-native)
- No persistent memory
- No knowledge base
- No proof verification
- Single model (Gemini only)
- No learning progression
- Early stage (many features in proposal phase)
- Heavy frontend dependencies

### Key Takeaway
The semantic graph concept is brilliant — seeing the STRUCTURE of an equation is different from seeing the equation. Should be adapted for CLI (ASCII/graphviz rendering).

---

## 5. AIMv2 (TheoryFoundry)
**Repo:** github.com/TheoryFoundry/AIMv2

### Strengths
- Theorem graph with proof dependencies
- Two reviewer modes (simple parallel, progressive recursive)
- Session persistence with theorem tracking
- Rust CLI (fast, single binary)
- Workspace-scoped file access
- Session logs for full audit trail

### Weaknesses
- No memory beyond session
- No knowledge base
- No visualization
- No MCP integration
- Limited to proof exploration
- No physics support
- No learning adaptation
- Minimal documentation

### Key Takeaway
Theorem graph + review modes are great for verification. The dependency tracking between results is valuable.

---

## 6. AI4Math (YSDA/Yandex)
**Repo:** zenodo.org/records/20306277

### Strengths
- Lean 4 proof verification (formal proofs!)
- Mathlib premise retrieval
- PDF reading for paper ingestion
- Web search integration
- Interactive REPL
- Inference-agnostic (any LLM backend)

### Weaknesses
- Focused on formal math only (no physics)
- Lean 4 has steep learning curve
- No memory system
- No visualization
- No learning progression
- Limited documentation
- Academic tool, not learner-focused

### Key Takeaway
Formal verification (Lean 4) is the ultimate rigor. Could be optional for advanced users.

---

# Gap Analysis: What's Missing for the Vision

## Carlo's Vision
"A CLI space to study, explore, and reason through complex topics together with AI agents that use MCP, skills, and evolve with learning."

## Critical Gaps Across ALL Tools

### 1. No MCP Integration
None of these tools use MCP. This means:
- No persistent memory across sessions (like EverMemOS)
- No tool composability
- No integration with existing workflows (Obsidian, Notion, etc.)

### 2. No Learning Evolution
None adapt to the learner. They're either:
- Static (same behavior every session)
- Or research-focused (one-shot problems, not learning arcs)

Missing: spaced repetition, difficulty curves, concept dependency tracking, "you struggled with X, let's revisit".

### 3. No Multi-Model Orchestration
Most are single-model. None use different models for different tasks:
- Fast model for definitions/explanations
- Strong model for proofs/derivations
- Vision model for diagram analysis
- Local model for privacy-sensitive notes

### 4. No Concept Graph
None track the DAG of concepts:
- "To understand Lagrangian mechanics, you need calculus of variations"
- "You mastered Newtonian mechanics but struggled with Hamiltonian"
- Spaced repetition based on the graph

### 5. No Interactive Exploration with Verification
The gap between "explore freely" and "verify rigorously" is unfilled. You want:
- Free-form conversation AND formal verification
- "What if I try this approach?" AND "Let me verify that step"
- Visual exploration AND symbolic computation

### 6. No CLI-Native Visualization
All visualization is web-based. Missing:
- Terminal-rendered plots (plotext, textual-plotext)
- ASCII art for equations and graphs
- Graphviz/dot for concept maps and proof trees
- Rich terminal UI (textual) for interactive exploration

### 7. No Integration with Personal Knowledge Systems
None connect to:
- reMarkable tablet for handwritten notes
- Obsidian vaults for linked knowledge
- Notion for structured documents
- Personal reading lists

## What We Need to Build

A unified CLI that combines:
- **DeepTutor's** 3-layer memory + KB + capability model
- **Alethic's** Generate-Verify-Revise loop + SymPy sandbox
- **PhysicsIntern's** multi-agent roles + research methodology
- **AlgeBench's** semantic graph concept (adapted for CLI)
- **AIMv2's** theorem graph + review modes
- **AI4Math's** formal verification (optional Lean 4)

Plus new:
- MCP integration (EverMemOS, Obsidian, etc.)
- Concept graph with spaced repetition
- Multi-model orchestration
- CLI-native visualization (rich + plotext)
- Skills that evolve with usage
- reMarkable integration for handwritten work
