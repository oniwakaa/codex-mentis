# Pitagora — Product Design & Roadmap

> From Codex Mentis (math reasoning tool) → **Pitagora** (interactive teaching harness for complex topics)

---

## 1. REBRAND: Codex Mentis → Pitagora

**Why Pitagora**: Pythagoras — the philosopher-mathematician who believed numbers were the essence of all things. Bridges math, philosophy, and the teaching tradition (Pythagorean schools were the first "guided learning communities").

### Rename scope
| What | From | To |
|------|------|----|
| Python package | `codex_mentis/` | `pitagora/` |
| CLI entry point | `codex-mentis` | `pitagora` |
| Config dir | `~/.codex-mentis/` | `~/.pitagora/` |
| pyproject.toml name | `codex-mentis` | `pitagora` |
| All imports | `from codex_mentis...` | `from pitagora...` |
| All references in docs/yaml/tests | `codex_mentis` | `pitagora` |
| GitHub repo | `oniwakaa/codex-mentis` | `oniwakaa/pitagora` |

### Visual Identity
- **ASCII banner** on startup: stylized "PITAGORA" with a triangle (△) motif — the Pythagorean symbol
- **Color palette**: Deep indigo (#1a1a3e) + gold (#ffd700) + white — evokes ancient mathematical manuscripts
- **Prompt**: `△ pitagora>` instead of generic `>>>`
- **Tagline**: "Think. Prove. Understand."

---

## 2. ASSESSMENT: What We Have vs. What We Need

### ✅ What's Solid (Keep & Build On)

| Component | Status | Quality |
|-----------|--------|---------|
| Concept Graph (50+ concepts, 12 domains) | Working | ★★★★ |
| Mastery Tracker + ZPD | Working | ★★★★ |
| SM-2 Spaced Repetition | Working | ★★★★ |
| Multi-Agent Orchestrator | Working | ★★★ |
| YAML Workflow System (5 workflows) | Working | ★★★ |
| SymPy Math Engine + Verification | Working | ★★★★ |
| Terminal Plots (plotext) | Working | ★★ |
| Knowledge Base (RAG) | Working | ★★★ |
| User Graph | Working | ★★ |
| LaTeX Rendering | Working | ★★★ |
| Session/Memory Store | Working | ★★★ |
| 105 Tests | Passing | ★★★★ |

### 🔴 Critical Gaps (Must Fix)

#### Gap 1: NO INTERACTIVE PEDAGOGY
**Problem**: The `teach.yaml` workflow runs as a one-shot pipeline: explain → quiz → track. The Socratic tutor asks ONE question and the workflow ends. There's no conversation loop.

**What's needed**: A multi-turn guided learning session where:
- Agent explains a sub-concept
- Waits for user response
- Analyzes the response (understands it? confused? partially?)
- Adapts the next step accordingly
- Repeats until the concept is understood
- The user controls pacing ("go deeper", "skip", "explain differently")

**Current state**: `chat.py` has a REPL loop, but it doesn't know it's in "teaching mode". The agent just responds to messages without structured pedagogical state.

#### Gap 2: NO ADAPTIVE DIFFICULTY
**Problem**: `user_graph.py` tracks `knowledge_level` but nothing reads it to calibrate output. Level is a static parameter passed at workflow start.

**What's needed**:
- Real-time difficulty calibration based on user responses
- If user gets 3 answers right → increase complexity
- If user says "I don't understand" → simplify, use more analogies
- Track "comprehension signals" from user messages (confusion keywords, correct/incorrect answers)
- Dynamic switching between explanation styles (Feynman → formal → visual → analogy)

#### Gap 3: NO INTERACTIVE VISUALIZATION
**Problem**: `plots.py` uses plotext for terminal bar/line charts. `latex_render.py` exists but isn't integrated into teaching. The visualizer agent mostly generates text descriptions.

**What's needed**:
- **Step-by-step visual derivations** (like 3Blue1Brown): animate an equation building up
- **Interactive parameter exploration**: "Drag" a variable and see how it affects the graph
- **Concept map rendering**: Show the dependency tree visually so the user sees where they are
- **Equation rendering in context**: Show LaTeX inline during explanations
- Options: Rich terminal widgets, browser-based (open a local HTML page with plotly/d3), or both

#### Gap 4: NO PHILOSOPHY / CROSS-DOMAIN REASONING
**Problem**: Concepts.yaml covers STEM only. No logic, epistemology, ethics, or philosophical reasoning.

**What's needed**:
- Philosophy domain in concepts.yaml (logic → propositional → predicate → modal → epistemology → metaphysics)
- A "reasoning" workflow that handles philosophical arguments (premise → inference → counter-argument → synthesis)
- Cross-domain connections ("How does Gödel's incompleteness relate to epistemological limits?")

#### Gap 5: NO GUIDED EXPLORATION MODE
**Problem**: The `/explore` command exists but there's no "guided journey" mode where the agent leads the user through a topic with interactive checkpoints.

**What's needed**:
- `/explore <topic>` starts a structured journey
- Agent presents a "map" of the topic (what we'll cover, what you'll learn)
- At each checkpoint, agent asks a question or presents a visualization
- User can branch off ("tell me more about X") and the agent adjusts the journey
- Journey state is saved so you can resume later

#### Gap 6: NO LEARNING SESSION CONTINUITY
**Problem**: Sessions exist but aren't structured as learning journeys. No way to "resume where you left off" in a topic.

**What's needed**:
- Learning Journey = persistent object (topic, progress, checkpoints, mastery updates)
- Save/load journeys
- Dashboard: "You have 3 active journeys: Calculus (60%), Quantum (20%), Logic (40%)"

---

## 3. PRODUCT DESIGN: The Pitagora Experience

### User Journey: "I want to understand Lagrangian Mechanics"

```
$ pitagora

    ██████╗ ██╗████████╗ █████╗  ██████╗  ██████╗ ██████╗  █████╗ 
    ██╔══██╗██║╚══██╔══╝██╔══██╗██╔════╝ ██╔═══██╗██╔══██╗██╔══██╗
    ██████╔╝██║   ██║   ███████║██║  ███╗██║   ██║██████╔╝███████║
    ██╔═══╝ ██║   ██║   ██╔══██║██║   ██║██║   ██║██╔══██╗██╔══██║
    ██║     ██║   ██║   ██║  ██║╚██████╔╝╚██████╔╝██║  ██║██║  ██║
    ╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
    ▸ Think. Prove. Understand.
    
    Welcome back, Carlo. You have 2 concepts due for review.
    Active journeys: Calculus (75%), Quantum Mechanics (30%)
    
△ pitagora> explore Lagrangian Mechanics

    ╭──────────────────────────────────────────────────────╮
    │  🗺️  Learning Journey: Lagrangian Mechanics          │
    │                                                      │
    │  Prerequisites:                                      │
    │  ✅ Newton's Laws (mastered)                         │
    │  ✅ Multivariable Calculus (mastered)                 │
    │  ⬜ Variational Calculus (not started)               │
    │                                                      │
    │  What we'll cover:                                   │
    │  1. The Principle of Least Action                    │
    │  2. Generalized Coordinates                          │
    │  3. The Lagrangian (L = T - V)                       │
    │  4. Euler-Lagrange Equations                         │
    │  5. Conservation Laws & Symmetries                   │
    │                                                      │
    │  Your level: Intermediate                            │
    │  Estimated time: 45 min                              │
    │                                                      │
    │  [Enter] Start  [s] Skip to topic  [l] Change level  │
    ╰──────────────────────────────────────────────────────╯

△ pitagora> enter

    ▸ Let's start with intuition. You know Newton's Laws:
      F = ma. For each body, you track forces, write equations,
      solve. Works great for simple systems.
    
      But what happens with a double pendulum? A bead on a 
      rotating wire? Constraint forces get ugly fast.
    
      Lagrange had a radical insight: forget forces. Think 
      about ENERGY instead.
    
      🔑 Key idea: The path a system takes between two points
      is the one that makes the ACTION stationary.
    
      [n] Next  [e] Explain differently  [d] Go deeper  [?] I'm confused

△ pitagora> d

    ▸ "Stationary" here means the derivative is zero — like
      finding the top of a hill. Not minimum necessarily,
      just... flat.
    
      Think of it like this: imagine you're hiking between
      two valleys. You could take infinite paths. Nature 
      "chooses" the path where the total walking effort has
      zero derivative — neither increasing nor decreasing
      at any point.
    
      Mathematically:
    
      S = ∫ L(q, q̇, t) dt    (the Action)
      
      where L = T - V (kinetic minus potential energy)
    
      The actual path satisfies δS = 0
    
      [📊 See this visualized]  [n] Next  [e] Different analogy
```

### Core Interaction Modes

| Mode | Command | Description |
|------|---------|-------------|
| **Explore** | `/explore <topic>` | Guided learning journey with checkpoints |
| **Solve** | `/solve <problem>` | Multi-step derivation with verification |
| **Debate** | `/debate <thesis>` | Adversarial reasoning on a claim |
| **Review** | `/review` | Spaced repetition session |
| **Dashboard** | `/dashboard` | Visual overview of learning progress |
| **Chat** | (default) | Free-form Q&A with context-aware responses |

---

## 4. FEATURE DESIGN: What to Build

### P0 — Must Have (Make it a Teaching Tool)

#### F1: Teaching Session Engine
**The core feature. Replaces one-shot workflows with interactive loops.**

```
Architecture:
  TeachingSession
    ├── state: str  (introducing, exploring, checking, adapting, reviewing)
    ├── topic: ConceptNode
    ├── user_level: Level  (auto-detected + user-adjustable)
    ├── interaction_history: List[Interaction]
    ├── comprehension_score: float  (0.0 → 1.0)
    └── next_step() → TeachingAction
```

- Each TeachingAction = one agent turn (explain, question, visualize, quiz)
- After each action, WAIT for user input
- Analyze user response:
  - Correct answer → bump comprehension, advance
  - Partial understanding → reinforce with different angle
  - Confusion → simplify, add analogy, go back
  - "Skip" → advance but flag for later review
  - "Deeper" → add mathematical rigor, show proofs
- Session state persists across `/explore` calls

#### F2: Response Analyzer
**Understands what the user means, not just what they say.**

- Classify user responses: `correct`, `partial`, `confused`, `skip`, `deeper`, `different_style`, `question`, `off_topic`
- Use LLM for classification (not keyword matching)
- Track comprehension trend over session
- Feed into difficulty calibration

#### F3: Adaptive Prompting System
**Dynamically adjusts explanation style based on user signals.**

Styles (rotated based on effectiveness):
1. **Feynman** — Simple language, everyday analogies
2. **Formal** — Mathematical rigor, definitions, theorems
3. **Visual** — Graphs, diagrams, concept maps
4. **Historical** — How the concept was discovered, by whom, why
5. **Socratic** — Questions that lead to self-discovery
6. **Applied** — Real-world examples and problems

Track which style works best per user per domain. The self-improver agent already tracks strategies — wire it into the teaching loop.

#### F4: Terminal Visualization Overhaul
**Replace bare plotext with Rich-powered interactive displays.**

- **Concept Map**: Rich tree widget showing dependency graph with mastery colors (green/yellow/red)
- **Equation Blocks**: Rendered LaTeX in bordered Rich panels
- **Step-by-step Derivation**: Annotated equation sequences with explanations
- **Progress Bars**: Per-concept mastery gauges
- **Interactive Plots**: Generate HTML with plotly → open in browser, or use Rich canvas for simple terminal plots
- **Journey Map**: Visual path through the topic with checkpoints

#### F5: Identity & First Impression
- ASCII art banner (triangle + PITAGORA)
- Color theme (indigo/gold)
- Styled prompt (`△ pitagora>`)
- Welcome screen with active journeys + review reminders
- `/about` command with philosophy of the tool

### P1 — Should Have (Make it Stick)

#### F6: Learning Journeys (Persistent)
- Journey = topic + progress + checkpoints + mastery state
- Save to `~/.pitagora/journeys/`
- Resume with `/explore --continue <journey>`
- `/dashboard` shows all journeys with progress

#### F7: Philosophy Domain
- Add to concepts.yaml: logic → propositional → predicate → modal → epistemology → metaphysics → ethics
- Philosophy workflow: thesis → argument → counter-argument → synthesis → reflection
- Cross-domain connections: "This mathematical concept connects to this philosophical idea because..."

#### F8: Spaced Repetition Integration
- After each teaching session, automatically create review cards
- `/review` opens a focused review session (not just flashcards — interactive quizzing)
- Review uses the same adaptive system (adjusts question difficulty)

#### F9: Multi-Modal Explanations
- For each concept, generate:
  - Text explanation (current)
  - Analogy (current)
  - Visual diagram (NEW)
  - Historical context (NEW)
  - Practice problem (current)
  - "Teach it back" prompt (NEW — user explains it to the agent)
- Agent selects the right combination based on user response patterns

### P2 — Nice to Have (Polish)

#### F10: Browser Dashboard
- Local web UI (FastAPI + HTMX or similar)
- Visual concept graph (D3.js force-directed)
- Learning journey timeline
- Mastery heat map across all domains
- Rich terminal for chat, browser for visualization

#### F11: Knowledge Ingestion → Auto-Teach
- `/ingest <url/pdf>` → extract concepts → auto-create learning journey
- "I found these 5 concepts in this paper. Want me to teach you them?"

#### F12: Collaborative Features
- Export a learning journey as a shareable document
- "Teach mode" where the agent prepares a structured lesson

---

## 5. IMPLEMENTATION PLAN

### Phase 1: Rebrand + Identity (1-2 days)
- [ ] Rename package `codex_mentis/` → `pitagora/`
- [ ] Update all imports, pyproject.toml, config paths
- [ ] ASCII banner + color theme
- [ ] Styled prompt
- [ ] Welcome screen with status
- [ ] Update tests
- [ ] Rename GitHub repo

### Phase 2: Teaching Session Engine (3-5 days)
- [ ] `TeachingSession` class (state machine for interactive teaching)
- [ ] Response analyzer (classify user input)
- [ ] Adaptive prompting (style selection)
- [ ] Wire into chat.py REPL as a mode
- [ ] `/explore <topic>` command → starts TeachingSession
- [ ] Session persistence (save/load teaching state)
- [ ] Tests for teaching flow

### Phase 3: Visualization + UX (2-3 days)
- [ ] Concept map renderer (Rich tree with colors)
- [ ] Equation block renderer (LaTeX in Rich panels)
- [ ] Step-by-step derivation display
- [ ] Journey map visualization
- [ ] Mastery dashboard (`/dashboard`)
- [ ] Progress indicators everywhere

### Phase 4: Learning Journeys + Persistence (1-2 days)
- [ ] Journey model (topic, progress, checkpoints, mastery)
- [ ] Save/load journeys to disk
- [ ] `/explore --continue` to resume
- [ ] `/journeys` to list active journeys
- [ ] Wire spaced repetition into post-session flow

### Phase 5: Philosophy Domain + Cross-Domain (2-3 days)
- [ ] Philosophy concepts in concepts.yaml
- [ ] Philosophy reasoning workflow
- [ ] Cross-domain connection engine
- [ ] `/debate` command for philosophical reasoning

### Phase 6: Polish + Browser Dashboard (3-5 days)
- [ ] Browser-based concept graph (D3.js)
- [ ] Interactive parameter exploration
- [ ] Export/import journeys
- [ ] Performance optimization
- [ ] Full test suite update

---

## 6. TECHNICAL DECISIONS

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Rebrand scope | Full rename (package, CLI, config) | Do it once, do it right |
| Teaching state machine | In-process, not YAML workflow | Needs real-time interactivity, YAML is for batch |
| Visualization | Rich (terminal) + optional browser | Terminal-first, browser as enhancement |
| Response analysis | LLM-based classification | Nuanced understanding, not keyword matching |
| Journey persistence | JSON files in `~/.pitagora/journeys/` | Simple, human-readable, git-friendly |
| Philosophy reasoning | Same agent framework, new workflow YAML | Consistent architecture |
| Interactive plots | plotly → HTML → browser (primary), plotext (fallback) | Real interactivity requires a canvas |

---

## 7. SUCCESS CRITERIA

1. **Identity**: You run `pitagora` and immediately know what it is
2. **Teaching**: You can explore a topic interactively for 30+ minutes and come away understanding it
3. **Adaptation**: The agent adjusts its style when you're confused vs. breezing through
4. **Visualization**: Complex concepts have visual representations, not just text
5. **Continuity**: You can stop and resume a learning journey days later
6. **Breadth**: Math, physics, AND philosophy are first-class domains
7. **Sticky**: The spaced repetition ensures you don't forget what you learned

---

*Pitagora — because understanding is not a destination, it's a journey.*
