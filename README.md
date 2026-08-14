# 🧠 Pitagora

> **Latin: "Book of the Mind"** — An AI-powered CLI for studying, exploring, and reasoning through complex mathematics and physics.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ What is Pitagora?

Pitagora is not just another AI chatbot wrapper. It's a **multi-agent reasoning system** designed specifically for learning and exploring mathematics and physics. It features:

- **🎯 Specialized AI Agents** — Tutor (Socratic teaching), Researcher (deep dives), Prover (formal derivations), Reviewer (adversarial verification), Explainer (multi-level explanations), and Self-Improver (learns what works for YOU)
- **📐 SymPy Sandbox** — Every mathematical claim is verified computationally in an isolated sandbox
- **🔄 Generate-Verify-Revise** — Proofs go through a rigorous loop: generate → verify with SymPy → fix errors → re-verify
- **📊 Interactive Concept Graph** — Visual DAG of math/physics concepts with mastery tracking and adaptive learning paths
- **🧩 Side-by-Side Reasoning** — See technical derivation AND plain English intuition simultaneously
- **🧠 3-Layer Memory** — Session traces, per-topic knowledge, and cross-topic synthesis that persists across sessions
- **📈 Spaced Repetition** — SM-2 algorithm schedules reviews of concepts you're forgetting
- **🔬 Self-Improving** — Tracks which explanations work for you and evolves its strategies using Thompson Sampling
- **🖥️ Beautiful TUI** — Full Textual terminal UI with interactive widgets, not just a text REPL

## 🚀 Installation

```bash
# Core CLI and Rich fallback
pip install pitagora

# Full-screen Textual chat
pip install 'pitagora[tui]'

# All optional features
pip install 'pitagora[all]'
```

`pitagora` launches the TUI in a terminal, while `pitagora --simple` and `pitagora chat --simple` launch the Rich REPL.

### Quick Start

```bash
# Launch the interactive TUI (default)
pitagora

# Or use the short alias
cm

# Simple readline mode (Rich fallback)
pitagora --simple
pitagora chat --simple
pitagora study "Lagrangian mechanics"
pitagora explore "What happens if gravity was 2x?"
pitagora derive "Euler-Lagrange equation from principle of least action"
pitagora verify "The eigenvalues of a Hermitian matrix are real"
pitagora explain "Riemann hypothesis" --level beginner
pitagora plot "sin(x) * e^(-x)" --range 0 10
pitagora concept map "quantum mechanics"
```

## 🤖 Agents

### Tutor Agent
Socratic teaching style — asks guiding questions instead of giving direct answers. Adapts to your level.

### Research Agent  
Deep-dive research with web search and knowledge base retrieval. Structured reports with citations.

### Prover Agent
Rigorous mathematical derivations with SymPy verification. Uses Generate-Verify-Revise loop.

### Reviewer Agent
Adversarial review — actively tries to find counterexamples and edge cases.

### Explainer Agent
Breaks down complex topics at 5 levels (child → expert). Uses Feynman technique. Creates intuition maps.

### Self-Improver Agent
Tracks your learning outcomes. A/B tests explanation strategies. Evolves prompts based on what works for you using Thompson Sampling.

### Visualizer Agent
Terminal plots, interactive concept maps, proof trees, and equation rendering.

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Pitagora CLI / TUI                       │
├────────────┬────────────┬────────────┬────────────────────────┤
│  Study     │  Explore   │  Reason    │  Verify │  Visualize   │
├────────────┴────────────┴────────────┴────────────────────────┤
│                   Agent Orchestrator                             │
│   (Parallel workflows, Debate mode, Pipeline mode, Side-by-side)│
├────────┬─────────┬─────────┬──────────┬─────────┬──────────────┤
│ Tutor  │Research │ Prover  │ Reviewer │Explainer│Self-Improver │
├────────┴─────────┴─────────┴──────────┴─────────┴──────────────┤
│                      Core Services                               │
├────────┬─────────┬─────────┬──────────┬─────────┬──────────────┤
│ Memory │ Concept │   KB/   │  Skills  │  Math   │  Providers   │
│ System │  Graph  │   RAG   │  Engine  │  Engine │  (Multi-LLM) │
├────────┴─────────┴─────────┴──────────┴─────────┴──────────────┤
│                   Integration Layer (MCP)                        │
├────────┬─────────┬─────────┬──────────┬────────────────────────┤
│EverMemOS│Obsidian│ Notion  │reMarkable│   ArXiv  │  Web Search │
└────────┴─────────┴─────────┴──────────┴────────────────────────┘
```

## ⚙️ Configuration

```yaml
# ~/.pitagora/config.yaml
providers:
  default: gemini           # General tasks
  reasoning: openai         # Complex proofs
  vision: anthropic         # Diagram analysis
  local: ollama             # Privacy-sensitive tasks

memory:
  backend: sqlite
  vector_model: all-MiniLM-L6-v2
  spaced_repetition: true

math:
  sandbox: sympy
  verification_levels: [computational, cross_check]
  plot_backend: plotext

ui:
  theme: dark
  latex: true
  plots: terminal
```

### Supported Providers

| Provider | Models | Local/Cloud |
|----------|--------|-------------|
| OpenAI | GPT-4o, GPT-4, GPT-3.5 | Cloud |
| Anthropic | Claude 3.5 Sonnet, Claude 3 Opus | Cloud |
| Google | Gemini 1.5 Pro/Flash | Cloud |
| Ollama | Llama 3, Mistral, Phi-3, etc. | Local |
| llama.cpp | Any GGUF model | Local |

## 🎓 Learning Modes

### Study Mode
Structured learning with the Tutor agent using Socratic method. Spaced repetition schedules reviews. Concept mastery is tracked.

### Explore Mode
Free-form investigation. The Research agent searches papers, KB, and web to build understanding.

### Reason Mode
Formal derivations with the Prover agent. Every step is verified by SymPy. Errors are caught and fixed automatically.

### Verify Mode
Adversarial review with the Reviewer agent. Claims are tested against edge cases and counterexamples.

### Side-by-Side Mode
Run any topic through parallel agents: technical derivation on the left, plain English intuition on the right.

## 🧪 Example Sessions

```bash
# Study with Socratic guidance
$ pitagora study "Euler-Lagrange equation"
> Tutor: Let's start with the principle of least action. What do you 
> think "least action" physically means? Why would nature prefer a 
> path that minimizes (or extremizes) a quantity?

# Verify a claim  
$ pitagora verify "Every continuous function is differentiable"
> Reviewer: VERDICT: REFUTED (Confidence: 0.99)
> Counterexample: f(x) = |x| is continuous everywhere but not 
> differentiable at x=0.

# Side-by-side derivation
$ pitagora derive "Schrödinger equation from de Broglie hypothesis"
> ┌─────────────────────────┬──────────────────────────────┐
> │ TECHNICAL DERIVATION    │ INTUITION                    │
> │                         │                              │
> │ 1. de Broglie: λ = h/p │ Matter waves have a          │
> │ 2. ψ = Ae^(ikx-iωt)   │ wavelength inversely         │
> │ 3. k = p/ℏ, ω = E/ℏ   │ proportional to momentum     │
> │ ...                     │ ...                          │
> └─────────────────────────┴──────────────────────────────┘
```

## 📜 License

MIT License — See [LICENSE](LICENSE) for details.

---

*Built with SymPy, Rich, Textual, and a deep love for mathematics.* 🎓
