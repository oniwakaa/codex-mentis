# Pitagora — Full Implementation Brief

> Interactive teaching harness for mathematics, physics, and philosophy.
> Repo: `~/projects/codex-mentis/` (will become `pitagora/` after rename)

## What This Project Is

Pitagora (formerly "Codex Mentis") is a CLI-based teaching tool that uses multi-agent LLM orchestration to guide users through complex topics — math, physics, philosophy — with interactive Socratic dialogue, SymPy-verified derivations, spaced repetition, and adaptive difficulty.

**Current state**: 16K+ LOC, 105 tests, working REPL with RAG/concept graph/spaced repetition/SymPy. But it's a **tool** (ask a question, get an answer), not a **teacher** (guide someone through understanding). The goal is to transform it into a real interactive teaching harness.

**Provider**: CLIProxy at `http://localhost:8317/v1`, key `cliproxy-sk-local`, model `google/gemini-3.6-flash-high` (OpenAI-compatible API).

**Already done** (committed, don't re-implement): ASCII banner in gold, `show_pitagora_banner()` and `show_welcome()` in `rich_ui.py`, styled prompt `△ pitagora>`, rebranded system prompt in `chat.py`.

---

## TASK 1: Full Package Rename (codex_mentis → pitagora) — DO FIRST

Rename the Python package from `codex_mentis` to `pitagora`. This is mechanical but touches every file.

### What to rename:

| What | From | To |
|------|------|----|
| Python package dir | `codex_mentis/` | `pitagora/` |
| All imports in all .py files | `from codex_mentis.` / `import codex_mentis.` | `from pitagora.` / `import pitagora.` |
| pyproject.toml | name, entry points, package dirs | `pitagora` |
| Config directory path | `~/.codex-mentis/` | `~/.pitagora/` |
| All config path references in code | `~/.codex-mentis` (string literals in ~15 files) | `~/.pitagora` |
| Test files | All 4 root-level + all 20 under `tests/` | Update imports |
| Display strings | `Codex Mentis` | `Pitagora` |
| CLI help strings | `codex-mentis` | `pitagora` |
| Env var | `CM_MODEL` | `PITAGORA_MODEL` |
| Error messages | `codex-mentis setup` | `pitagora setup` |
| Docs | README.md, ANALYSIS.md, ARCHITECTURE.md, INTEGRATION.md | Update all mentions |

### Watch out for:

- `CONFIG_DIR` in `core/config.py` — after rename, all files should import from a single constant, not hardcode the path
- `codex_mentis` appearing inside strings (error messages, config paths, YAML references)
- The `self_improver.db` file in repo root — leave as-is (it's a data file, not a package reference)

### Verification:

```bash
cd ~/projects/codex-mentis
python -m pytest tests/ -x
```

All tests must pass after rename.

---

## TASK 2: Teaching Session Engine (THE CORE FEATURE)

The current `chat.py` REPL is a basic message→response loop. We need an **interactive teaching mode** where the agent guides the user through topics with back-and-forth dialogue, adapting based on user responses.

### Architecture Overview

```
User types /explore Lagrangian Mechanics
    → TeachingSession created (topic, level, sub-concepts)
    → Agent presents topic overview
    → Agent explains first sub-concept
    → Shows controls: [n] Next [e] Explain differently [d] Go deeper [?] Confused [s] Skip
    → User responds (either chat or control shortcut)
    → ResponseAnalyzer classifies the response via LLM
    → TeachingSession updates state, comprehension score, picks next action
    → Loop until all sub-concepts covered
    → Summary + spaced repetition cards created
    → Journey saved for resume later
```

### 2a: TeachingSession State Machine

Create `pitagora/teaching/__init__.py` (empty) and `pitagora/teaching/session.py`:

```python
"""Interactive teaching session with state machine."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


@dataclass
class Interaction:
    """A single agent↔user interaction."""
    action_type: str          # "explain", "question", "visualize", "quiz"
    style: str                # "feynman", "formal", "visual", etc.
    sub_concept: str          # which sub-concept was being taught
    agent_output: str         # what the agent said
    user_input: str           # what the user said (or shortcut like "n", "d")
    classification: str       # "correct", "partial", "confused", "skip", "deeper", "question"
    comprehension_delta: float
    timestamp: str


class TeachingSession:
    """
    Interactive teaching session state machine.
    
    States:
        INTRODUCING → EXPLORING ↔ CHECKING ↔ ADAPTING
                                    ↓
                              VISUALIZING / QUIZZING
                                    ↓
                                  REVIEWING → done
        Any state → PAUSED (save & resume later)
    """
    
    # State constants
    INTRODUCING = "introducing"
    EXPLORING = "exploring"
    CHECKING = "checking"
    ADAPTING = "adapting"
    VISUALIZING = "visualizing"
    QUIZZING = "quizzing"
    REVIEWING = "reviewing"
    PAUSED = "paused"
    COMPLETED = "completed"
    
    # Explanation styles
    STYLES = ["feynman", "formal", "visual", "historical", "socratic", "applied"]
    
    def __init__(self, topic: str, user_level: str = "intermediate"):
        self.id = str(uuid.uuid4())[:8]
        self.topic = topic
        self.user_level = user_level
        self.state = self.INTRODUCING
        self.comprehension_score = 0.5  # 0.0 to 1.0
        self.interaction_history: List[Interaction] = []
        self.sub_concepts: List[Dict[str, Any]] = []
        # Each sub-concept: {"name": str, "status": "pending"|"active"|"mastered"|"skipped",
        #                     "mastery_score": float, "interactions": int}
        self.current_sub_concept_idx = 0
        self.style_effectiveness: Dict[str, float] = {s: 0.5 for s in self.STYLES}
        self.preferred_style: Optional[str] = None  # User can set this
        self.journey_id: Optional[str] = None
        self.created_at = datetime.utcnow().isoformat()
        self.last_active = self.created_at
        self.total_interactions = 0
    
    @property
    def current_sub_concept(self) -> Optional[str]:
        if 0 <= self.current_sub_concept_idx < len(self.sub_concepts):
            return self.sub_concepts[self.current_sub_concept_idx]["name"]
        return None
    
    @property
    def progress_pct(self) -> float:
        if not self.sub_concepts:
            return 0.0
        done = sum(1 for sc in self.sub_concepts if sc["status"] in ("mastered", "skipped"))
        return done / len(self.sub_concepts)
    
    def set_sub_concepts(self, concepts: List[str]) -> None:
        """Set the ordered list of sub-concepts to cover."""
        self.sub_concepts = [
            {"name": c, "status": "pending", "mastery_score": 0.0, "interactions": 0}
            for c in concepts
        ]
        if self.sub_concepts:
            self.sub_concepts[0]["status"] = "active"
    
    def next_action(self) -> Dict[str, Any]:
        """
        Determine the next teaching action based on current state.
        
        Returns:
            {"type": "explain"|"question"|"visualize"|"quiz"|"review"|"complete",
             "style": str,
             "prompt_hint": str,
             "sub_concept": str,
             "state": str}
        """
        if self.state == self.INTRODUCING:
            return {
                "type": "explain",
                "style": "feynman",
                "prompt_hint": "introduce_topic",
                "sub_concept": self.topic,
                "state": self.state,
            }
        
        if self.state == self.EXPLORING:
            style = self.preferred_style or self._best_style()
            return {
                "type": "explain",
                "style": style,
                "prompt_hint": "explain_sub_concept",
                "sub_concept": self.current_sub_concept,
                "state": self.state,
            }
        
        if self.state == self.CHECKING:
            return {
                "type": "question",
                "style": "socratic",
                "prompt_hint": "check_understanding",
                "sub_concept": self.current_sub_concept,
                "state": self.state,
            }
        
        if self.state == self.VISUALIZING:
            return {
                "type": "visualize",
                "style": "visual",
                "prompt_hint": "show_visualization",
                "sub_concept": self.current_sub_concept,
                "state": self.state,
            }
        
        if self.state == self.QUIZZING:
            return {
                "type": "quiz",
                "style": "applied",
                "prompt_hint": "generate_problem",
                "sub_concept": self.current_sub_concept,
                "state": self.state,
            }
        
        if self.state == self.REVIEWING:
            return {
                "type": "review",
                "style": "feynman",
                "prompt_hint": "summarize_learning",
                "sub_concept": self.topic,
                "state": self.state,
            }
        
        return {"type": "complete", "style": "", "prompt_hint": "", "sub_concept": "", "state": self.COMPLETED}
    
    def record_interaction(self, action_type: str, style: str, agent_output: str,
                           user_input: str, classification: str, comprehension_delta: float) -> None:
        """Record an interaction and update state."""
        interaction = Interaction(
            action_type=action_type,
            style=style,
            sub_concept=self.current_sub_concept or self.topic,
            agent_output=agent_output,
            user_input=user_input,
            classification=classification,
            comprehension_delta=comprehension_delta,
            timestamp=datetime.utcnow().isoformat(),
        )
        self.interaction_history.append(interaction)
        self.total_interactions += 1
        self.last_active = interaction.timestamp
        
        # Update comprehension
        self.comprehension_score = max(0.0, min(1.0, self.comprehension_score + comprehension_delta))
        
        # Update style effectiveness (moving average)
        if style in self.style_effectiveness:
            n = sum(1 for i in self.interaction_history if i.style == style)
            positive = sum(1 for i in self.interaction_history 
                          if i.style == style and i.classification in ("correct", "deeper"))
            self.style_effectiveness[style] = positive / n if n > 0 else 0.5
        
        # Update current sub-concept
        if 0 <= self.current_sub_concept_idx < len(self.sub_concepts):
            sc = self.sub_concepts[self.current_sub_concept_idx]
            sc["interactions"] += 1
            sc["mastery_score"] = max(0.0, min(1.0, sc["mastery_score"] + comprehension_delta))
    
    def advance(self) -> bool:
        """Move to next sub-concept. Returns False if all done."""
        if 0 <= self.current_sub_concept_idx < len(self.sub_concepts):
            sc = self.sub_concepts[self.current_sub_concept_idx]
            sc["status"] = "mastered" if sc["mastery_score"] >= 0.6 else "skipped"
        
        self.current_sub_concept_idx += 1
        if self.current_sub_concept_idx >= len(self.sub_concepts):
            self.state = self.REVIEWING
            return False
        
        self.sub_concepts[self.current_sub_concept_idx]["status"] = "active"
        self.state = self.EXPLORING
        self.comprehension_score = 0.5  # Reset for new sub-concept
        return True
    
    def process_shortcut(self, shortcut: str) -> str:
        """
        Process a user shortcut and return the appropriate state transition.
        
        Shortcuts:
            n / next → advance to next sub-concept
            e / explain → re-explain in different style
            d / deeper → add rigor to current explanation
            s / skip → skip current sub-concept
            ? / confused → simplify, switch to more intuitive style
            v / visualize → show visualization
            q / quiz → generate practice problem
        """
        shortcut = shortcut.strip().lower()
        
        if shortcut in ("n", "next"):
            if self.advance():
                return self.EXPLORING
            return self.REVIEWING
        
        elif shortcut in ("e", "explain", "different"):
            # Switch to next-best style
            self.preferred_style = self._next_style()
            return self.EXPLORING
        
        elif shortcut in ("d", "deeper", "deep"):
            self.preferred_style = "formal"
            return self.EXPLORING
        
        elif shortcut in ("s", "skip"):
            if self.advance():
                return self.EXPLORING
            return self.REVIEWING
        
        elif shortcut in ("?", "confused", "idk", "don't understand"):
            self.preferred_style = "feynman"
            self.comprehension_score = max(0.0, self.comprehension_score - 0.2)
            return self.EXPLORING
        
        elif shortcut in ("v", "visual", "visualize"):
            return self.VISUALIZING
        
        elif shortcut in ("q", "quiz", "practice"):
            return self.QUIZZING
        
        else:
            # It's a free-text response — let the analyzer handle it
            return self.state
    
    def _best_style(self) -> str:
        """Return the most effective style so far."""
        return max(self.style_effectiveness, key=self.style_effectiveness.get)
    
    def _next_style(self) -> str:
        """Return a different style from the current preferred."""
        current = self.preferred_style or self._best_style()
        styles = [s for s in self.STYLES if s != current]
        # Pick the most effective of the alternatives
        return max(styles, key=lambda s: self.style_effectiveness.get(s, 0.5))
    
    def save(self) -> Dict[str, Any]:
        """Serialize session state for persistence."""
        return {
            "id": self.id,
            "topic": self.topic,
            "user_level": self.user_level,
            "state": self.state,
            "comprehension_score": self.comprehension_score,
            "sub_concepts": self.sub_concepts,
            "current_sub_concept_idx": self.current_sub_concept_idx,
            "style_effectiveness": self.style_effectiveness,
            "preferred_style": self.preferred_style,
            "journey_id": self.journey_id,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "total_interactions": self.total_interactions,
            "interaction_history": [
                {
                    "action_type": i.action_type, "style": i.style,
                    "sub_concept": i.sub_concept, "agent_output": i.agent_output[:500],
                    "user_input": i.user_input[:200], "classification": i.classification,
                    "comprehension_delta": i.comprehension_delta, "timestamp": i.timestamp,
                }
                for i in self.interaction_history
            ],
        }
    
    @classmethod
    def load(cls, data: Dict[str, Any]) -> 'TeachingSession':
        """Restore session from saved state."""
        session = cls(data["topic"], data.get("user_level", "intermediate"))
        session.id = data["id"]
        session.state = data.get("state", cls.INTRODUCING)
        session.comprehension_score = data.get("comprehension_score", 0.5)
        session.sub_concepts = data.get("sub_concepts", [])
        session.current_sub_concept_idx = data.get("current_sub_concept_idx", 0)
        session.style_effectiveness = data.get("style_effectiveness", {s: 0.5 for s in cls.STYLES})
        session.preferred_style = data.get("preferred_style")
        session.journey_id = data.get("journey_id")
        session.created_at = data.get("created_at", "")
        session.last_active = data.get("last_active", "")
        session.total_interactions = data.get("total_interactions", 0)
        return session
```

### 2b: Response Analyzer

Create `pitagora/teaching/analyzer.py`:

```python
"""Analyzes user responses during teaching sessions using LLM classification."""
from typing import Dict, Any, Optional


class ResponseAnalyzer:
    """
    Classifies user responses in a teaching context.
    
    Uses LLM calls (NOT keyword matching) for nuanced understanding.
    """
    
    CLASSIFICATION_PROMPT = """You are analyzing a student's response during an interactive teaching session.

Topic: {topic}
Sub-concept being taught: {concept}
Explanation style used: {style}
Student's response: "{response}"

Classify the student's response as EXACTLY ONE of these categories:
- correct: Student demonstrates clear understanding of the concept
- partial: Student grasps some parts but is confused or wrong about others
- confused: Student is clearly lost or misunderstands the concept
- skip: Student wants to move on to the next topic
- deeper: Student wants more mathematical rigor, detail, or depth
- question: Student is asking a clarifying question
- off_topic: Student changed the subject entirely

Respond with ONLY a JSON object:
{{"classification": "<category>", "confidence": <0.0-1.0>, "brief": "<one sentence explanation>"}}
"""
    
    COMPREHENSION_DELTAS = {
        "correct": 0.15,
        "partial": 0.0,
        "confused": -0.2,
        "skip": -0.05,
        "deeper": 0.05,
        "question": 0.0,
        "off_topic": -0.05,
    }
    
    # Map shortcuts directly (no LLM call needed)
    SHORTCUT_MAP = {
        "n": "skip", "next": "skip",
        "e": "partial", "explain": "partial", "different": "partial",
        "d": "correct", "deeper": "correct", "deep": "correct",
        "s": "skip", "skip": "skip",
        "?": "confused", "confused": "confused", "idk": "confused",
        "v": "question", "visual": "question", "visualize": "question",
        "q": "question", "quiz": "question", "practice": "question",
    }
    
    def __init__(self, chat_completion_fn=None):
        """
        Args:
            chat_completion_fn: Function(messages, model, config) → str
                                If None, falls back to shortcut detection only.
        """
        self.chat_completion = chat_completion_fn
    
    def classify(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify a user response.
        
        Args:
            user_input: What the user typed
            context: {"topic": str, "concept": str, "style": str}
        
        Returns:
            {"classification": str, "confidence": float, "brief": str,
             "comprehension_delta": float}
        """
        stripped = user_input.strip().lower()
        
        # Fast path: shortcuts
        if stripped in self.SHORTCUT_MAP:
            cls = self.SHORTCUT_MAP[stripped]
            return {
                "classification": cls,
                "confidence": 1.0,
                "brief": f"User shortcut: {stripped}",
                "comprehension_delta": self.COMPREHENSION_DELTAS[cls],
            }
        
        # LLM path: classify free-text responses
        if self.chat_completion:
            try:
                prompt = self.CLASSIFICATION_PROMPT.format(
                    topic=context.get("topic", "unknown"),
                    concept=context.get("concept", "unknown"),
                    style=context.get("style", "unknown"),
                    response=user_input,
                )
                messages = [{"role": "user", "content": prompt}]
                raw = self.chat_completion(messages)
                
                # Parse JSON response
                import json
                # Extract JSON from response (handle markdown code blocks)
                text = raw.strip()
                if "```" in text:
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()
                
                parsed = json.loads(text)
                cls = parsed.get("classification", "partial")
                if cls not in self.COMPREHENSION_DELTAS:
                    cls = "partial"
                
                return {
                    "classification": cls,
                    "confidence": parsed.get("confidence", 0.7),
                    "brief": parsed.get("brief", ""),
                    "comprehension_delta": self.COMPREHENSION_DELTAS[cls],
                }
            except Exception:
                pass
        
        # Fallback: heuristic
        return {
            "classification": "partial",
            "confidence": 0.3,
            "brief": "Could not classify response",
            "comprehension_delta": 0.0,
        }
```

### 2c: Teaching UI Widgets

Create `pitagora/teaching/ui.py`:

```python
"""Rich UI widgets for the teaching experience."""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.tree import Tree
from typing import Dict, List, Any, Optional

console = Console()


def show_teaching_controls(state: str, preferred_style: Optional[str] = None) -> None:
    """Show interactive controls based on current teaching state."""
    controls = []
    
    if state in ("exploring", "introducing"):
        controls.append("[bold cyan]n[/bold cyan] Next")
        controls.append("[bold cyan]e[/bold cyan] Explain differently")
        controls.append("[bold cyan]d[/bold cyan] Go deeper")
        controls.append("[bold yellow]?[/bold yellow] I'm confused")
        controls.append("[bold cyan]s[/bold cyan] Skip")
        controls.append("[bold cyan]v[/bold cyan] Visualize")
        controls.append("[bold cyan]q[/bold cyan] Quiz me")
    elif state == "checking":
        controls.append("[bold cyan]Type your answer[/bold cyan]")
        controls.append("[bold yellow]?[/bold yellow] I'm confused")
    elif state == "quizzing":
        controls.append("[bold cyan]Type your solution[/bold cyan]")
        controls.append("[bold yellow]?[/bold yellow] Hint please")
    elif state == "reviewing":
        controls.append("[bold cyan]n[/bold cyan] Continue")
    
    if preferred_style:
        controls.append(f"[dim]Style: {preferred_style}[/dim]")
    
    if controls:
        console.print(f"  {'  '.join(controls)}", style="dim")


def show_comprehension_gauge(score: float, sub_concept: str = "") -> None:
    """Show a visual comprehension indicator."""
    bar_len = 15
    filled = int(score * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    
    if score >= 0.8:
        color = "green"
        emoji = "✅"
    elif score >= 0.5:
        color = "yellow"
        emoji = "📊"
    else:
        color = "red"
        emoji = "📉"
    
    label = f" — {sub_concept}" if sub_concept else ""
    console.print(f"  {emoji} [{color}]{bar}[/{color}] {score*100:.0f}%{label}", highlight=False)


def show_sub_concept_progress(current_idx: int, total: int, name: str) -> None:
    """Show progress through sub-concepts."""
    console.print(f"  [bold]▸ {current_idx + 1}/{total}:[/bold] {name}", highlight=False)


def show_topic_overview(topic: str, sub_concepts: List[str], user_level: str,
                        prerequisites_met: List[str] = None) -> None:
    """Show the teaching journey overview panel."""
    lines = [f"[bold gold1]🗺️  Learning Journey: {topic}[/bold gold1]", ""]
    
    if prerequisites_met:
        lines.append("[bold]Prerequisites:[/bold]")
        for p in prerequisites_met:
            lines.append(f"  ✅ {p}")
        lines.append("")
    
    lines.append(f"[bold]What we'll cover:[/bold]")
    for i, sc in enumerate(sub_concepts, 1):
        lines.append(f"  {i}. {sc}")
    
    lines.append("")
    lines.append(f"Your level: [cyan]{user_level}[/cyan]")
    lines.append("")
    lines.append("[bold cyan]Enter[/bold cyan] Start  "
                 "[bold cyan]s[/bold cyan] Skip to topic  "
                 "[bold cyan]l[/bold cyan] Change level")
    
    console.print(Panel("\n".join(lines), border_style="gold1", expand=False))


def show_session_summary(topic: str, sub_concepts: List[Dict], total_interactions: int,
                         style_effectiveness: Dict[str, float]) -> None:
    """Show end-of-session summary."""
    lines = [f"[bold gold1]📋 Session Summary: {topic}[/bold gold1]", ""]
    
    mastered = sum(1 for sc in sub_concepts if sc.get("status") == "mastered")
    lines.append(f"Sub-concepts: {mastered}/{len(sub_concepts)} mastered")
    lines.append(f"Interactions: {total_interactions}")
    lines.append("")
    
    # Best style
    best = max(style_effectiveness, key=style_effectiveness.get)
    lines.append(f"Most effective style: [cyan]{best}[/cyan] ({style_effectiveness[best]*100:.0f}%)")
    lines.append("")
    
    # Sub-concept breakdown
    for sc in sub_concepts:
        status = sc.get("status", "pending")
        icon = "✅" if status == "mastered" else "⏭️" if status == "skipped" else "⬜"
        score = sc.get("mastery_score", 0)
        lines.append(f"  {icon} {sc['name']} ({score*100:.0f}%)")
    
    console.print(Panel("\n".join(lines), border_style="gold1", expand=False))


def show_journey_map(concept_graph, mastery_tracker, topic: str = None) -> None:
    """Show concept dependency tree with mastery colors."""
    # This is a simplified version — the agent should enhance it
    # based on the actual ConceptGraph API
    tree = Tree("[bold gold1]📚 Knowledge Map[/bold gold1]")
    
    if concept_graph and hasattr(concept_graph, 'graph'):
        for domain, concepts in concept_graph.graph.items():
            domain_node = tree.add(f"[bold]{domain}[/bold]")
            for concept_id, details in concepts.items() if isinstance(concepts, dict) else []:
                mastery = 0.0
                if mastery_tracker:
                    try:
                        mastery = mastery_tracker.get_mastery(concept_id)
                    except Exception:
                        pass
                
                name = details.get("name", concept_id) if isinstance(details, dict) else concept_id
                if mastery >= 0.8:
                    style = "green"
                elif mastery >= 0.5:
                    style = "yellow"
                elif mastery > 0:
                    style = "red"
                else:
                    style = "dim"
                
                marker = "▸" if topic and concept_id == topic else " "
                domain_node.add(f"[{style}]{marker} {name} ({mastery*100:.0f}%)[/{style}]")
    
    console.print(tree)
```

### 2d: Chat Integration

Modify `pitagora/chat.py` to wire in the teaching engine. Add these changes:

1. **Import at top of file**:
```python
from pitagora.teaching.session import TeachingSession
from pitagora.teaching.analyzer import ResponseAnalyzer
from pitagora.teaching.ui import (
    show_teaching_controls, show_comprehension_gauge,
    show_sub_concept_progress, show_topic_overview, show_session_summary
)
```

2. **Add teaching state to launch_chat**:
```python
def launch_chat(mode="study", topic="general", system_prompt=None):
    # ... existing setup ...
    teaching_session: Optional[TeachingSession] = None
    analyzer = ResponseAnalyzer(chat_completion_fn=chat_completion)
```

3. **Add /explore command handler** (inside the command handling block):
```python
elif cmd == "/explore":
    if not arg:
        console.print("[dim]Usage: /explore <topic>[/dim]")
        continue
    
    # Check for existing journey
    try:
        from pitagora.journeys.store import list_journeys
        journeys = list_journeys()
        existing = [j for j in journeys if j.get("topic", "").lower() == arg.lower() 
                    and j.get("status") == "active"]
        if existing:
            # Load existing session
            journey = existing[0]
            teaching_session = TeachingSession.load(journey.get("session_state", {}))
            teaching_session.journey_id = journey["id"]
            console.print(f"[green]Resuming journey: {arg}[/green]")
        else:
            teaching_session = TeachingSession(arg)
    except Exception:
        teaching_session = TeachingSession(arg)
    
    # Get sub-concepts from concept graph or generate via LLM
    try:
        from pitagora.concepts.graph import ConceptGraph
        cg = ConceptGraph()
        if arg.lower() in [k.lower() for k in cg.graph.keys()]:
            path = cg.get_learning_path(arg)
            teaching_session.set_sub_concepts(path if path else [arg])
        else:
            # Generate sub-concepts via LLM
            sub_concept_prompt = (
                f"Break down the topic '{arg}' into 5-8 ordered sub-concepts for teaching. "
                f"Return ONLY a JSON array of strings, ordered from foundational to advanced."
            )
            raw = chat_completion([{"role": "user", "content": sub_concept_prompt}])
            import json
            try:
                subs = json.loads(raw.strip().strip("`").replace("json", "").strip())
                teaching_session.set_sub_concepts(subs)
            except Exception:
                teaching_session.set_sub_concepts([arg])
    except Exception:
        teaching_session.set_sub_concepts([arg])
    
    # Show overview
    show_topic_overview(arg, [sc["name"] for sc in teaching_session.sub_concepts],
                       teaching_session.user_level)
    
    # Start first action
    action = teaching_session.next_action()
    teaching_session.state = teaching_session.EXPLORING
    continue
```

4. **Teaching mode main loop** (replace/augment the main chat flow):
```python
# ─── MAIN CHAT FLOW ───
if teaching_session and teaching_session.state not in (TeachingSession.PAUSED, TeachingSession.COMPLETED):
    # TEACHING MODE
    shortcut_states = ("exploring", "introducing", "checking", "quizzing", "reviewing")
    
    # Process shortcut if applicable
    if user_input.strip().lower() in ("n", "next", "e", "explain", "d", "deeper", 
                                       "s", "skip", "?", "confused", "v", "visual", "q", "quiz"):
        new_state = teaching_session.process_shortcut(user_input)
        if new_state == "reviewing":
            # Show summary
            show_session_summary(
                teaching_session.topic,
                teaching_session.sub_concepts,
                teaching_session.total_interactions,
                teaching_session.style_effectiveness,
            )
            # Save journey
            try:
                from pitagora.journeys.store import save_journey
                from pitagora.journeys.model import LearningJourney
                journey = LearningJourney(
                    topic=teaching_session.topic,
                    status="completed",
                    session_state=teaching_session.save(),
                )
                save_journey(journey)
            except Exception:
                pass
            teaching_session = None
            continue
    
    # Get next teaching action
    action = teaching_session.next_action()
    
    # Build teaching prompt
    teaching_prompt = _build_teaching_prompt(action, teaching_session, user_input)
    teaching_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": "user" if i % 2 == 0 else "assistant", "content": 
         i_obj.user_input if i % 2 == 0 else i_obj.agent_output}
        for i, i_obj in enumerate(teaching_session.interaction_history[-6:])
    ]
    teaching_messages.append({"role": "user", "content": teaching_prompt})
    
    with console.status("[bold cyan]Thinking...[/bold cyan]"):
        response = chat_completion(teaching_messages, model=model, config=config)
    
    # Display
    console.print()
    console.print(Markdown(response))
    console.print()
    
    # Show comprehension + controls
    show_comprehension_gauge(teaching_session.comprehension_score,
                            teaching_session.current_sub_concept)
    show_teaching_controls(teaching_session.state, teaching_session.preferred_style)
    
    # Record (classification happens on next iteration when user responds)
    # For now, record the agent's output
    teaching_session.record_interaction(
        action_type=action["type"],
        style=action["style"],
        agent_output=response,
        user_input=user_input,
        classification="partial",  # Will be updated on next response
        comprehension_delta=0.0,
    )
    
    # Auto-save
    try:
        from pitagora.journeys.store import save_journey, load_journey
        if teaching_session.journey_id:
            journey = load_journey(teaching_session.journey_id)
            if journey:
                journey["session_state"] = teaching_session.save()
                save_journey(journey)
    except Exception:
        pass

else:
    # NORMAL MODE (existing chat flow — don't change)
    rag_ctx = _get_rag_context(user_input)
    # ... rest of existing flow ...
```

5. **Teaching prompt builder**:
```python
def _build_teaching_prompt(action: dict, session: TeachingSession, user_input: str) -> str:
    """Build the LLM prompt for a teaching action."""
    style_instructions = {
        "feynman": "Explain in simple terms using everyday analogies. Avoid jargon. Make it intuitive.",
        "formal": "Use precise mathematical language, definitions, and theorems. Show equations.",
        "visual": "Describe or create a visual representation. Use ASCII diagrams, describe graphs, show patterns.",
        "historical": "Tell the story of how this concept was discovered. Who figured it out and why?",
        "socratic": "Guide through questions. Don't give the answer — lead the student to discover it.",
        "applied": "Show real-world applications and concrete examples.",
    }
    
    style = action.get("style", "feynman")
    instructions = style_instructions.get(style, style_instructions["feynman"])
    
    prompt_parts = [
        f"Teaching topic: {session.topic}",
        f"Current sub-concept: {action.get('sub_concept', session.topic)}",
        f"Student level: {session.user_level}",
        f"Comprehension: {session.comprehension_score*100:.0f}%",
        f"Explanation style: {style} — {instructions}",
    ]
    
    if action["prompt_hint"] == "introduce_topic":
        prompt_parts.append("Provide an engaging overview of this topic. Hook the student's curiosity.")
    elif action["prompt_hint"] == "explain_sub_concept":
        prompt_parts.append(f"Explain the sub-concept: {action.get('sub_concept')}")
        if session.comprehension_score < 0.3:
            prompt_parts.append("The student is struggling. Simplify significantly. Use more analogies.")
    elif action["prompt_hint"] == "check_understanding":
        prompt_parts.append("Ask ONE question to check if the student understands. Don't give the answer.")
    elif action["prompt_hint"] == "show_visualization":
        prompt_parts.append("Create a clear visual representation of this concept. Use ASCII art if helpful.")
    elif action["prompt_hint"] == "generate_problem":
        prompt_parts.append("Generate a practice problem. Give the problem and hints only, not the solution.")
    elif action["prompt_hint"] == "summarize_learning":
        prompt_parts.append("Summarize what the student has learned. Highlight key insights.")
    
    if user_input and user_input.strip().lower() not in ("n", "e", "d", "s", "?", "v", "q"):
        prompt_parts.append(f"\nStudent said: \"{user_input}\"")
    
    return "\n".join(prompt_parts)
```

6. **Add /journeys and /dashboard commands**:
```python
elif cmd == "/journeys":
    try:
        from pitagora.journeys.store import list_journeys
        journeys = list_journeys()
        if not journeys:
            console.print("[dim]No learning journeys yet. Use /explore <topic> to start.[/dim]")
        else:
            for j in journeys:
                status_icon = "🟢" if j.get("status") == "active" else "✅" if j.get("status") == "completed" else "⏸️"
                console.print(f"  {status_icon} {j.get('topic', '?')} — {j.get('status', '?')}")
    except Exception as e:
        console.print(f"[dim]Journeys unavailable: {e}[/dim]")
    continue

elif cmd == "/dashboard":
    try:
        from pitagora.journeys.store import list_journeys
        journeys = list_journeys()
        from pitagora.concepts.graph import ConceptGraph
        cg = ConceptGraph()
        from pitagora.cli.rich_ui import show_mastery_dashboard
        show_mastery_dashboard(cg, journeys)
    except Exception as e:
        console.print(f"[dim]Dashboard unavailable: {e}[/dim]")
    continue
```

---

## TASK 3: Learning Journeys (Persistent Progress)

### 3a: Journey Model

Create `pitagora/journeys/__init__.py` (empty) and `pitagora/journeys/model.py`:

```python
"""Learning journey data model."""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid


@dataclass
class LearningJourney:
    """A persistent learning journey across sessions."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = ""
    status: str = "active"  # "active", "paused", "completed", "abandoned"
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_active: str = ""
    user_level: str = "intermediate"
    sub_concepts: List[Dict[str, Any]] = field(default_factory=list)
    # Each: {"name": str, "status": str, "mastery_score": float, "interactions": int}
    current_idx: int = 0
    comprehension_history: List[Dict[str, Any]] = field(default_factory=list)
    # Each: {"timestamp": str, "score": float, "sub_concept": str}
    style_effectiveness: Dict[str, float] = field(default_factory=dict)
    total_interactions: int = 0
    session_state: Dict[str, Any] = field(default_factory=dict)  # TeachingSession.save() data
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "status": self.status,
            "started_at": self.started_at,
            "last_active": self.last_active or self.started_at,
            "user_level": self.user_level,
            "sub_concepts": self.sub_concepts,
            "current_idx": self.current_idx,
            "comprehension_history": self.comprehension_history,
            "style_effectiveness": self.style_effectiveness,
            "total_interactions": self.total_interactions,
            "session_state": self.session_state,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearningJourney':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
```

### 3b: Journey Store

Create `pitagora/journeys/store.py`:

```python
"""Persistent storage for learning journeys."""
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pitagora.journeys.model import LearningJourney

JOURNEYS_DIR = Path("~/.pitagora/journeys").expanduser()


def _ensure_dir():
    JOURNEYS_DIR.mkdir(parents=True, exist_ok=True)


def save_journey(journey: LearningJourney) -> str:
    """Save a journey to disk. Returns the file path."""
    _ensure_dir()
    data = journey.to_dict() if isinstance(journey, LearningJourney) else journey
    path = JOURNEYS_DIR / f"{data['id']}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return str(path)


def load_journey(journey_id: str) -> Optional[LearningJourney]:
    """Load a journey by ID."""
    path = JOURNEYS_DIR / f"{journey_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return LearningJourney.from_dict(json.load(f))


def list_journeys(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all journeys, optionally filtered by status."""
    _ensure_dir()
    journeys = []
    for p in sorted(JOURNEYS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(p) as f:
                data = json.load(f)
            if status_filter and data.get("status") != status_filter:
                continue
            journeys.append(data)
        except Exception:
            continue
    return journeys


def delete_journey(journey_id: str) -> bool:
    """Delete a journey by ID."""
    path = JOURNEYS_DIR / f"{journey_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
```

---

## TASK 4: Philosophy Domain

### 4a: Add Philosophy Concepts

Append to `pitagora/data/concepts.yaml` (after rename):

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

```yaml
name: philosophical_reasoning
description: >
  Reasoning pipeline for philosophical questions: clarify terms,
  build arguments FOR, challenge with arguments AGAINST, synthesize,
  and connect to mathematical/scientific concepts.

inputs:
  - name: question
    description: The philosophical question or thesis to explore
    required: true
  - name: domain
    description: Philosophical domain (ethics, epistemology, metaphysics, logic, aesthetics)
    default: general

steps:
  - id: clarify
    agent: explainer
    prompt: |
      Clarify the philosophical question: "{{ question }}"
      1. Define all key terms precisely
      2. Identify the underlying assumptions
      3. State the question in its strongest form
      4. Identify what kind of answer would be satisfying (logical proof, empirical evidence, thought experiment, etc.)
    outputs: [clarified_question, key_terms, assumptions]

  - id: argue_for
    agent: prover
    prompt: |
      Build the strongest possible argument FOR the thesis:
      "{{ clarified_question }}"
      
      Key terms: {{ clarify.outputs.key_terms }}
      Assumptions: {{ clarify.outputs.assumptions }}
      
      Structure as:
      1. Premises (clearly stated)
      2. Logical chain of inference
      3. Conclusion
      
      Use formal logic notation where appropriate.
    inputs_from: [clarify]
    outputs: [argument_for, premises_for]

  - id: argue_against
    agent: debate
    prompt: |
      Build the strongest possible argument AGAINST the thesis:
      "{{ clarified_question }}"
      
      The argument FOR was: {{ argue_for.outputs.argument_for }}
      
      Find:
      1. Weak premises in the argument FOR
      2. Counter-examples
      3. Alternative interpretations
      4. A competing argument with its own premises and logic
    inputs_from: [clarify, argue_for]
    outputs: [argument_against, counter_examples]

  - id: synthesize
    agent: explainer
    prompt: |
      Synthesize the arguments for and against:
      
      Thesis: {{ clarified_question }}
      Argument FOR: {{ argue_for.outputs.argument_for }}
      Argument AGAINST: {{ argue_against.outputs.argument_against }}
      
      Provide:
      1. Where both sides agree (common ground)
      2. The crux of the disagreement
      3. A nuanced position that accounts for both
      4. Remaining open questions
    inputs_from: [clarify, argue_for, argue_against]
    outputs: [synthesis, open_questions]

  - id: connect
    agent: researcher
    prompt: |
      Connect this philosophical discussion to mathematics and science:
      
      Question: {{ clarified_question }}
      Synthesis: {{ synthesize.outputs.synthesis }}
      
      Find connections to:
      - Mathematical concepts (Gödel, computability, probability, etc.)
      - Physics (quantum mechanics, thermodynamics, cosmology)
      - Other philosophical traditions (Eastern philosophy, pragmatism, etc.)
      - Historical context (who else has grappled with this?)
    inputs_from: [clarify, synthesize]
    outputs: [connections, historical_context]

merge_strategy: combine
```

### 4c: Logic Skill

Create `pitagora/skills/builtin/logic.yaml`:

```yaml
name: logic
domain: philosophy
description: Formal logic — propositional calculus, truth tables, natural deduction
difficulty_levels:
  - beginner
  - intermediate
  - advanced

concepts:
  - id: logic_truth_tables
    name: Truth Tables
    description: Evaluating logical expressions by exhaustive enumeration
    key_equations:
      - "p ∧ q: true only when both p and q are true"
      - "p ∨ q: true when at least one of p, q is true"
      - "¬p: the negation of p"
      - "p → q: false only when p is true and q is false"
    exercises:
      - level: beginner
        prompt: "Build a truth table for (p → q) ∧ (q → p)"
      - level: intermediate
        prompt: "Prove that (p → q) ≡ (¬p ∨ q) using truth tables"
      - level: advanced
        prompt: "Show that {∧, ¬} is a functionally complete set"

  - id: logic_natural_deduction
    name: Natural Deduction
    description: Deriving conclusions from premises using inference rules
    key_equations:
      - "Modus Ponens: p, p → q ⊢ q"
      - "Modus Tollens: ¬q, p → q ⊢ ¬p"
      - "Hypothetical Syllogism: p → q, q → r ⊢ p → r"
    exercises:
      - level: beginner
        prompt: "Using modus ponens, derive q from: p, p → q"
      - level: intermediate
        prompt: "Prove: (p → q), (q → r), p ⊢ r"
      - level: advanced
        prompt: "Derive the law of excluded middle (p ∨ ¬p) in natural deduction"

  - id: logic_predicate_calculus
    name: Predicate Logic
    description: Extending propositional logic with quantifiers (∀, ∃)
    key_equations:
      - "∀x P(x): P holds for all x"
      - "∃x P(x): P holds for some x"
      - "¬∀x P(x) ≡ ∃x ¬P(x)"
      - "¬∃x P(x) ≡ ∀x ¬P(x)"
    exercises:
      - level: beginner
        prompt: "Translate: 'All cats are mammals' into predicate logic"
      - level: intermediate
        prompt: "Prove: ∀x(P(x) → Q(x)), ∃x P(x) ⊢ ∃x Q(x)"
      - level: advanced
        prompt: "Show that the set of valid formulas in first-order logic is recursively enumerable but not decidable"
```

---

## TASK 5: Visualization Improvements

### 5a: Enhanced Concept Map

Replace the existing `print_concept_map` in `pitagora/cli/rich_ui.py` with a version that shows mastery colors:

```python
def print_concept_map(concept_id: str, relations: Dict[str, List[str]], 
                      concept_names: Dict[str, str], 
                      mastery_scores: Dict[str, float] = None,
                      current_concept: str = None,
                      direction: str = "prerequisites") -> None:
    """Renders an ASCII concept dependency tree with mastery colors.
    
    Args:
        concept_id: Root concept
        relations: {concept_id: [prerequisite_ids]}
        concept_names: {concept_id: display_name}
        mastery_scores: {concept_id: float 0-1} for color coding
        current_concept: Which concept is currently being taught (marked with ▸)
        direction: "prerequisites" (upstream) or "dependents" (downstream)
    """
    mastery_scores = mastery_scores or {}
    root_name = concept_names.get(concept_id, concept_id)
    
    # Color based on mastery
    def _mastery_color(cid: str) -> str:
        score = mastery_scores.get(cid, -1)
        if score < 0:
            return "dim"
        if score >= 0.8:
            return "green"
        if score >= 0.5:
            return "yellow"
        return "red"
    
    def _label(cid: str) -> str:
        name = concept_names.get(cid, cid)
        color = _mastery_color(cid)
        marker = "▸ " if cid == current_concept else ""
        score_str = f" ({mastery_scores[cid]*100:.0f}%)" if cid in mastery_scores else ""
        return f"[{color}]{marker}{name}[/{color}]{score_str}"
    
    tree = Tree(_label(concept_id))
    
    def add_branches(node: Tree, cid: str, visited: set) -> None:
        if cid in visited:
            return
        visited.add(cid)
        children = relations.get(cid, [])
        for child in children:
            child_node = node.add(_label(child))
            add_branches(child_node, child, visited.copy())
    
    add_branches(tree, concept_id, set())
    console.print(tree)
```

### 5b: Equation Block Renderer

Add to `pitagora/cli/rich_ui.py`:

```python
def show_equation_block(equations: List[Dict[str, str]], title: str = "Derivation") -> None:
    """Render a sequence of equations as a derivation block.
    
    Args:
        equations: [{"equation": "E = mc²", "annotation": "Mass-energy equivalence"}]
        title: Panel title
    """
    lines = []
    for i, eq in enumerate(equations, 1):
        eq_str = eq.get("equation", "")
        annotation = eq.get("annotation", "")
        
        # Render equation with Unicode math
        rendered = print_math(eq_str, return_str=True) or eq_str
        
        if annotation:
            lines.append(f"  [bold yellow]{i}.[/bold yellow] {rendered}    [dim]← {annotation}[/dim]")
        else:
            lines.append(f"  [bold yellow]{i}.[/bold yellow] {rendered}")
    
    console.print(Panel("\n".join(lines), title=f"[bold]{title}[/bold]", border_style="yellow", expand=False))
```

Also update `print_math` to support a `return_str=True` parameter (returns the rendered string instead of printing).

### 5c: Mastery Dashboard

Add to `pitagora/cli/rich_ui.py`:

```python
def show_mastery_dashboard(concept_graph, journeys: list = None) -> None:
    """Show mastery overview grouped by domain."""
    from rich.table import Table
    
    table = Table(title="📊 Mastery Dashboard", show_header=True, header_style="bold gold1")
    table.add_column("Domain", style="bold")
    table.add_column("Concepts")
    table.add_column("Mastered")
    table.add_column("Progress")
    table.add_column("Status")
    
    # Group concepts by domain
    if hasattr(concept_graph, 'graph'):
        domains = {}
        for concept_id, details in concept_graph.graph.items():
            if isinstance(details, dict):
                domain = details.get("domain", "General")
                if domain not in domains:
                    domains[domain] = {"total": 0, "mastered": 0}
                domains[domain]["total"] += 1
                # Check mastery from tracker if available
                # domains[domain]["mastered"] += 1 if mastered
        
        for domain, stats in sorted(domains.items()):
            total = stats["total"]
            mastered = stats["mastered"]
            pct = (mastered / total * 100) if total > 0 else 0
            bar_len = 15
            filled = int(pct / 100 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            
            color = "green" if pct >= 80 else "yellow" if pct >= 40 else "red"
            status = "✅ Mastered" if pct >= 80 else "🔄 In Progress" if pct > 0 else "⬜ Not Started"
            
            table.add_row(domain, str(total), str(mastered), f"[{color}]{bar}[/{color}] {pct:.0f}%", status)
    
    console.print(table)
    
    # Show active journeys
    if journeys:
        console.print("\n[bold]Active Journeys:[/bold]")
        for j in journeys:
            if j.get("status") == "active":
                topic = j.get("topic", "?")
                subs = j.get("sub_concepts", [])
                done = sum(1 for s in subs if s.get("status") in ("mastered", "skipped"))
                console.print(f"  🟢 {topic} — {done}/{len(subs)} sub-concepts")
```

---

## TASK 6: Bug Fixes & Audit

### 6a: Integrate Orchestrator

The `agents/orchestrator.py` exists but is dead code — `chat.py` bypasses it. Add a `/workflow` command:

```python
elif cmd == "/workflow":
    if not arg:
        console.print("[dim]Usage: /workflow <name> [args]. Available: teach, derive_and_prove, concept_mastery, debate, deep_research, philosophical_reasoning[/dim]")
        continue
    
    parts = arg.split(" ", 1)
    workflow_name = parts[0]
    workflow_arg = parts[1] if len(parts) > 1 else ""
    
    try:
        from pitagora.agents.orchestrator import Orchestrator
        from pitagora.agents.explainer import ExplainerAgent
        from pitagora.agents.tutor import TutorAgent
        from pitagora.agents.prover import ProverAgent
        from pitagora.agents.reviewer import ReviewerAgent
        from pitagora.agents.visualizer import VisualizerAgent
        from pitagora.agents.researcher import ResearcherAgent
        from pitagora.agents.debate import DebateAgent
        
        agents = {
            "explainer": ExplainerAgent(),
            "tutor": TutorAgent(),
            "prover": ProverAgent(),
            "reviewer": ReviewerAgent(),
            "visualizer": VisualizerAgent(),
            "researcher": ResearcherAgent(),
            "debate": DebateAgent(),
        }
        
        orchestrator = Orchestrator(agents=agents)
        
        with console.status(f"[cyan]Running workflow: {workflow_name}...[/cyan]"):
            result = orchestrator.run_workflow(
                workflow_name,
                inputs={"topic": workflow_arg, "problem": workflow_arg, "question": workflow_arg}
            )
        
        console.print()
        console.print(Markdown(result.content if hasattr(result, 'content') else str(result)))
    except Exception as e:
        console.print(f"[red]Workflow error: {e}[/red]")
    continue
```

### 6b: Remove Empty Stubs

Either implement or remove:
- `pitagora/mcp_integration/__init__.py` — if empty, add a comment explaining it's reserved for future MCP integration
- `pitagora/cli/widgets/__init__.py` — if empty, add a comment or remove

### 6c: Config Path Consistency

After rename, ensure ALL config paths use a single constant. Add to `pitagora/core/constants.py`:

```python
from pathlib import Path

PITAGORA_DIR = Path("~/.pitagora").expanduser()
PITAGORA_CONFIG = PITAGORA_DIR / "config.yaml"
PITAGORA_DB = PITAGORA_DIR / "memory.db"
PITAGORA_JOURNEYS = PITAGORA_DIR / "journeys"
```

Then update all files that hardcode `~/.pitagora/` to import from `pitagora.core.constants`.

### 6d: Test Coverage

Add tests for new features:

- `tests/test_teaching_session.py` — Test state transitions, save/load, shortcut processing, comprehension tracking
- `tests/test_response_analyzer.py` — Test shortcut classification, fallback behavior
- `tests/test_learning_journeys.py` — Test save/load/list/delete
- `tests/test_philosophy_concepts.py` — Test that philosophy domain loads from YAML

---

## Implementation Order

1. **TASK 1** (rename) — Do FIRST. Everything depends on it.
2. **TASK 2a + 2b** (TeachingSession + ResponseAnalyzer) — Core logic
3. **TASK 3** (Learning Journeys) — Persistence layer
4. **TASK 2c + 2d** (UI widgets + Chat integration) — Wire it together
5. **TASK 4** (Philosophy) — New domain
6. **TASK 5** (Visualization) — Polish
7. **TASK 6** (Bugs) — Fix throughout

## Constraints

- **No new heavy dependencies**. Use what's in pyproject.toml (rich, httpx, pydantic, sqlite-utils, sympy, plotext, pyyaml).
- **Run `python -m pytest tests/ -x`** after each major task.
- **Don't break existing chat REPL**. Default free-form Q&A must still work.
- **Config dir**: `~/.pitagora/` after rename.
- **DB files**: `~/.pitagora/memory.db` for spaced repetition, `~/.pitagora/journeys/*.json` for journeys.
- **Already done** (don't re-implement): ASCII banner, gold theme, styled prompt, `show_pitagora_banner()`, `show_welcome()` in rich_ui.py, rebranded system prompt in chat.py. These are committed.
