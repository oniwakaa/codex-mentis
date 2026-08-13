"""Interactive chat REPL — the main user experience.

This is the core chat loop. It connects ALL systems:
- Provider (CLIProxy/Gemini/OpenAI/etc)
- Knowledge base (RAG — inject relevant context)
- Concept graph (track what user studies)
- User graph (personalize by level/mastery)
- SymPy sandbox (verify math claims)
- Memory (save/load conversations)
- Spaced repetition (trigger reviews)
"""
import logging
import os
from typing import Any

import httpx

from pitagora.core.constants import (
    CONFIG_PATH,
    DEFAULT_API_KEY,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
)

log = logging.getLogger(__name__)


def load_provider_config() -> dict[str, Any]:
    """Load provider configuration from config.yaml or environment."""
    import yaml

    config_path = CONFIG_PATH
    
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        providers = config.get("providers", {})
        provider_config = providers.get("config", {})
        if provider_config:
            return provider_config

    api_key = os.getenv("OPENAI_API_KEY", os.getenv("CLIPROXY_API_KEY", ""))
    base_url = os.getenv("OPENAI_BASE_URL", "")
    
    if base_url and api_key:
        return {
            "name": "cliproxy",
            "type": "openai_compatible",
            "base_url": base_url,
            "api_key": api_key,
            "default_model": os.getenv("PITAGORA_MODEL", DEFAULT_MODEL),
        }

    return {
        "name": "cliproxy",
        "type": "openai_compatible",
        "base_url": DEFAULT_BASE_URL,
        "api_key": DEFAULT_API_KEY,
        "default_model": DEFAULT_MODEL,
    }


def chat_completion(
    messages: list,
    model: str | None = None,
    config: dict | None = None,
    stream: bool = False,
) -> str:
    """Send a chat completion request and return the response."""
    if config is None:
        config = load_provider_config()

    base_url = config.get("base_url", DEFAULT_BASE_URL)
    api_key = config.get("api_key", DEFAULT_API_KEY)
    model = model or config.get("default_model", DEFAULT_MODEL)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.7,
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content
    except httpx.ConnectError:
        return "[Error: Cannot connect to API. Is CLIProxy running? Try `pitagora setup` to reconfigure.]"
    except httpx.TimeoutException:
        return "[Error: Request timed out. The model may be overloaded.]"
    except Exception as e:
        return f"[Error: {e}]"


def _build_feedback_loop():
    """Best-effort construction of the self-improving feedback loop components.

    Returns (improver, skill_evo, skills_engine), each possibly None. The
    improver uses a null provider — only its DB methods are needed here
    (record_interaction / select_strategy_for); LLM-based prompt revision is
    not invoked from the chat loop. All failures degrade gracefully so a
    missing DB or import never breaks the chat REPL.
    """
    improver = skill_evo = skills_engine = None
    try:
        from pitagora.agents.providers.base import BaseProvider, ProviderConfig
        from pitagora.agents.self_improver import SelfImproverAgent

        class _NullProvider(BaseProvider):
            def __init__(self):
                super().__init__(ProviderConfig(api_key="null", model="null"))

            def complete(self, messages, tools=None, temperature=0.7, response_format=None):
                return {"content": "", "tool_calls": []}

            async def acomplete(self, messages, tools=None, temperature=0.7, response_format=None):
                return {"content": "", "tool_calls": []}

            def stream(self, messages):
                yield ""

            async def astream(self, messages):
                yield ""

            def embed(self, texts):
                return [[0.0] for _ in texts]

            async def aembed(self, texts):
                return [[0.0] for _ in texts]

        improver = SelfImproverAgent(_NullProvider())
    except Exception as e:
        log.debug("feedback loop improver unavailable: %s", e)

    try:
        from pitagora.skills.engine import SkillsEngine
        from pitagora.skills.evolution import SkillEvolution
        skill_evo = SkillEvolution()
        skills_engine = SkillsEngine()
    except Exception as e:
        log.debug("feedback loop skill tracking unavailable: %s", e)

    return improver, skill_evo, skills_engine


# Map SelfImprover strategy names to TeachingSession styles for seeding.
_STRATEGY_TO_STYLE = {
    "socratic": "socratic",
    "feynman": "feynman",
    "formal_proof": "formal",
    "analogy": "feynman",
    "side_by_side": "feynman",
}


def _seed_session_style(session, improver) -> None:
    """Seed a new teaching session's initial style from cross-session metrics.

    Only applies when the improver has enough history (≥5 interactions) for the
    topic; otherwise the session keeps its default style and learns per-session.
    """
    if improver is None:
        return
    try:
        from pitagora.teaching.session import ALL_STYLES
        report = {r["strategy_used"]: r for r in improver.strategy_report(topic=session.topic)}
        total = sum(r.get("uses", 0) for r in report.values())
        if total < 5:
            return
        strategy = improver.select_strategy_for(session.topic, session.user_level)
        style = _STRATEGY_TO_STYLE.get(strategy)
        if style in ALL_STYLES:
            session.current_style = style
    except Exception as e:
        log.debug("session style seed failed: %s", e)


def _get_rag_context(query: str, max_tokens: int = 2000) -> str:
    """Retrieve relevant context from knowledge base for RAG."""
    try:
        from pitagora.knowledge.base import KnowledgeBase
        kb = KnowledgeBase()
        results = kb.search(query, limit=3)
        if not results:
            return ""
        
        context_parts = ["[Relevant knowledge from your documents:]"]
        for r in results:
            source = r.get("source", "Unknown")
            content = r.get("content", "")[:500]
            context_parts.append(f"- [{source}]: {content}")
        
        return "\n".join(context_parts)
    except Exception:
        return ""


def _get_concept_context(topic: str) -> str:
    """Get concept graph context — prerequisites, learning path."""
    try:
        from pitagora.concepts.graph import ConceptGraph
        cg = ConceptGraph()
        
        # Check if topic exists in graph
        if topic.lower() in [k.lower() for k in cg.graph]:
            prereqs = cg.get_prerequisites(topic)
            path = cg.get_learning_path(topic)
            if prereqs or path:
                parts = [f"[Concept graph for '{topic}':]"]
                if prereqs:
                    parts.append(f"  Prerequisites: {', '.join(prereqs)}")
                if path:
                    parts.append(f"  Learning path: {' → '.join(path[:5])}")
                return "\n".join(parts)
    except Exception:
        pass
    return ""


def _get_user_context() -> str:
    """Get user profile context — level, mastery, recent activity."""
    try:
        from pitagora.cli.commands.onboard import load_profile
        profile = load_profile()
        if not profile:
            return ""
        
        parts = [f"[User profile: {profile.get('name', 'Student')}]"]
        levels = profile.get("levels", {})
        for subj, level in levels.items():
            parts.append(f"  {subj}: {level}")
        
        interests = profile.get("interests", [])
        if interests:
            parts.append(f"  Interests: {', '.join(interests)}")
        
        return "\n".join(parts)
    except Exception:
        return ""


def _verify_math(response: str) -> str | None:
    """Check if response contains math claims and verify with SymPy.

    Logs unexpected errors instead of silently swallowing them; only the
    narrow SymPy sandbox failures (parse/evaluate) are treated as 'no
    verification available'.
    """
    import logging
    import re

    log = logging.getLogger(__name__)

    equations = re.findall(r'\$([^$]+)\$', response)
    if not equations:
        return None

    try:
        from pitagora.math_engine.sandbox import SymPySandbox
        sandbox = SymPySandbox()
    except Exception as e:
        # Sandbox unavailable — log and bail, don't swallow silently.
        log.warning("SymPy sandbox unavailable for verification: %s", e)
        return None

    verified = []
    for eq in equations[:3]:  # Check up to 3 equations
        try:
            result = sandbox.evaluate(eq)
            if result.verified:
                verified.append(f"  ✓ {eq} = {result.value}")
            elif result.error:
                verified.append(f"  ⚠ {eq}: {result.error}")
        except Exception as e:
            # Per-equation failure: log and skip, keep verifying the rest.
            log.warning("verification failed for '%s': %s", eq, e)
            verified.append(f"  ⚠ {eq}: verification error")
    if verified:
        return "[SymPy verification:]\n" + "\n".join(verified)
    return None


def _save_to_memory(role: str, content: str, topic: str = "general") -> None:
    """Save message to memory store."""
    try:
        from pitagora.core.models import MemoryEntry
        from pitagora.memory.store import MemoryStore
        store = MemoryStore()
        entry = MemoryEntry(
            layer="L1",
            content=f"[{role}] {content[:500]}",
            topic=topic,
        )
        store.create_memory_entry(entry)
    except Exception as e:
        log.debug("failed to save memory entry: %s", e)


def _record_study(topic: str, user_input: str) -> None:
    """Record study activity in user graph."""
    try:
        from pitagora.cli.commands.onboard import load_profile
        from pitagora.memory.user_graph import UserGraph
        profile = load_profile()
        if profile:
            ug = UserGraph()
            ug.record_study(profile.get("name", "default"), topic, duration_minutes=1)
    except Exception as e:
        log.debug("failed to record study activity: %s", e)


def _check_due_reviews() -> str | None:
    """Check if there are cards due for spaced repetition review."""
    try:
        from pitagora.memory.spaced_repetition import SpacedRepetition
        sr = SpacedRepetition()
        due = sr.get_due_reviews()
        if due and len(due) > 0:
            return f"📚 You have {len(due)} concepts due for review. Run `pitagora review start`."
    except Exception as e:
        log.debug("failed to check due reviews: %s", e)
    return None


# ─── Teaching mode helpers ──────────────────────────────────────────────

SUBCONCEPT_GEN_PROMPT = (
    "You are a curriculum designer. Break the given topic into 3 to 6 ordered "
    "sub-concepts that a learner should cover, from foundational to advanced. "
    "Return ONLY a JSON object: {\"sub_concepts\": [\"name1\", \"name2\", ...]}. "
    "No extra text, no markdown fences."
)

STYLE_GUIDES = {
    "feynman": "Use the Feynman technique: explain as if to a curious beginner, use analogies and plain language before formalism.",
    "formal": "Use a formal, rigorous style: precise definitions, theorems, and symbolic notation.",
    "visual": "Use a visual style: describe diagrams, geometric intuition, and spatial relationships in words.",
    "historical": "Use a historical style: motivate the concept through the problem its inventors were trying to solve.",
    "socratic": "Use a Socratic style: lead the learner with guiding questions rather than stating answers directly.",
    "applied": "Use an applied style: ground the concept in a concrete real-world example or computation.",
}


def _generate_sub_concepts(topic: str, config: dict[str, Any], model: str) -> list[str]:
    """Ask the LLM to decompose a topic into ordered sub-concepts."""
    messages = [
        {"role": "system", "content": SUBCONCEPT_GEN_PROMPT},
        {"role": "user", "content": f"Topic: {topic}"},
    ]
    raw = chat_completion(messages, model=model, config=config)
    import json as _json
    try:
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("\n", 1)[-1] if "\n" in s else s
            if s.endswith("```"):
                s = s[:-3].strip()
        obj = _json.loads(s)
        subs = obj.get("sub_concepts", [])
        if isinstance(subs, list) and subs:
            return [str(x) for x in subs][:6]
    except Exception:
        pass
    # ponytail: fallback if LLM unparseable. Add graph-derived path here later.
    return [f"Foundations of {topic}", f"Core ideas of {topic}", f"Applications of {topic}"]


def _build_teaching_prompt(session, action: str, style: str) -> str:
    """Build the user-side instruction for the next teaching turn."""
    sc = session.current_subconcept
    sc_name = sc.name if sc else session.topic
    guide = STYLE_GUIDES.get(style, STYLE_GUIDES["feynman"])
    action_intro = {
        "introduce": f"Introduce the sub-concept '{sc_name}'. Give a short, clear motivation and definition.",
        "explain": f"Explain the sub-concept '{sc_name}'. {guide}",
        "check": f"Check the learner's understanding of '{sc_name}'. Pose a focused question or small exercise and wait for their answer.",
        "adapt": f"The learner needs a different angle on '{sc_name}'. {guide} Address the likely misconception directly.",
        "visualize": f"Describe a visualization or diagram for '{sc_name}' in words, then explain what it shows.",
        "quiz": f"Give a short quiz problem on '{sc_name}'. State the problem, then offer hints. Do NOT reveal the solution yet.",
        "review": f"Review what we covered. Summarize the key ideas of '{session.topic}' and the sub-concepts visited.",
        "advance": f"We are moving on to the next sub-concept: '{sc_name}'. Introduce it briefly.",
        "complete": f"Wrap up the session on '{session.topic}'. Summarize and suggest next steps.",
    }.get(action, f"Continue teaching '{sc_name}'. {guide}")
    return (
        f"{action_intro}\n\n"
        f"[Teaching context] topic: {session.topic} | sub-concept: {sc_name} | "
        f"comprehension: {session.comprehension_score:.2f} | style: {style} | "
        f"learner level: {session.user_level}\n"
        f"Keep it concise and focused. Use LaTeX for any equations."
    )


def _run_teaching_turn(console, session, analyzer, user_input, config, model, messages,
                       improver=None, skill_evo=None, skills_engine=None):
    """Process one teaching-mode turn: classify, update session, build prompt,
    call LLM, display response + controls. Mutates `messages` and `session`.

    When `improver`/`skill_evo`/`skills_engine` are supplied, the turn feeds the
    self-improving feedback loop with a real quality signal derived from the
    ResponseAnalyzer classification (WS1) and records matched skill usage (WS3a).
    """
    from rich.markdown import Markdown

    from pitagora.teaching.ui import (
        show_comprehension_gauge,
        show_controls,
        show_subconcept_progress,
    )

    sc = session.current_subconcept
    sc_name = sc.name if sc else session.topic

    # Classify (shortcuts bypass the LLM)
    result = analyzer.classify(user_input, session.topic, sc_name, config=config, model=model)
    session.apply_classification(result.label, result.delta, style=session.current_style)

    # WS1: feed the cross-session feedback loop with a real quality signal
    # derived from the learner's classified reply (not a neutral default).
    if improver is not None:
        try:
            from pitagora.agents.self_improver import quality_from_classification
            improver.record_interaction(
                topic=session.topic,
                level=session.user_level,
                strategy_used=session.current_style,
                response_quality=quality_from_classification(result.label),
                success=result.delta > 0,
            )
        except Exception as e:
            log.debug("feedback loop record_interaction failed: %s", e)

    # WS3a: record matched skill usage with the same success signal.
    if skill_evo is not None and skills_engine is not None and user_input != "begin":
        try:
            matched = skills_engine.match_skills(session.topic, user_input)
            if matched:
                skill_evo.record_use(
                    matched[0].name, success=result.delta > 0,
                    feedback=result.label, topic=session.topic,
                )
        except Exception as e:
            log.debug("skill usage record failed: %s", e)

    # Decide next action
    action = session.next_action(result.label)
    # Pick style: prefer the learner's best style once we have data, else current.
    style = session.style_effectiveness.best() if any(
        session.style_effectiveness.attempts.values()
    ) else session.current_style
    session.current_style = style

    # State transitions driven by the action
    from pitagora.teaching.session import TeachingState
    if action == "adapt":
        session.transition(TeachingState.adapting)
    elif action == "check":
        session.transition(TeachingState.checking)
    elif action == "visualize":
        session.transition(TeachingState.visualizing)
    elif action == "quiz":
        session.transition(TeachingState.quizzing)
    elif action == "review":
        session.transition(TeachingState.reviewing)
    elif action == "complete":
        session.complete()

    prompt = _build_teaching_prompt(session, action, style)
    messages.append({"role": "user", "content": prompt})

    with console.status("[bold cyan]Teaching...[/bold cyan]"):
        response = chat_completion(messages, model=model, config=config)
    messages.append({"role": "assistant", "content": response})

    console.print()
    console.print(Markdown(response))
    console.print()
    show_comprehension_gauge(session.comprehension_score, console)
    show_subconcept_progress(
        [sc.to_dict() for sc in session.sub_concepts],
        session.current_index,
        console,
    )
    show_controls(console)
    console.print()
    return response


def launch_chat(
    mode: str = "study",
    topic: str = "general",
    system_prompt: str | None = None,
    simple: bool = False,
) -> None:
    """Launch the interactive chat REPL with all systems connected."""
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    console = Console()
    config = load_provider_config()
    model = config.get("default_model", "unknown")

    # Build system prompt with context
    if system_prompt is None:
        system_prompt = (
            "You are Pitagora, an expert mathematics and physics tutor. "
            "You explain concepts clearly using the Socratic method — ask guiding questions "
            "before giving answers. Use LaTeX notation for equations ($..$ inline, $$...$$ display). "
            "Be precise, rigorous, and encouraging. When a student makes a mistake, "
            "guide them to discover the error rather than just correcting it. "
            "Use markdown formatting for structure."
        )

    # Inject user context into system prompt
    user_ctx = _get_user_context()
    if user_ctx:
        system_prompt += f"\n\n{user_ctx}"

    messages = [{"role": "system", "content": system_prompt}]

    # Teaching-mode state. None when in default free-form chat.
    teaching_session = None
    teaching_analyzer = None
    teaching_journey = None  # set in TASK 3 wiring

    # WS1/WS3a feedback loop: cross-session strategy metrics + skill usage.
    # Best-effort; stays None if the DB or imports are unavailable.
    feedback_improver, feedback_skill_evo, feedback_skills_engine = _build_feedback_loop()
    # Last free-form response context (topic, strategy) for the /rate command.
    last_freeform = {"topic": topic, "strategy": "socratic"}

    # Welcome — gold ASCII banner + info panel.
    from pitagora.cli.rich_ui import show_welcome
    show_welcome(mode=mode, topic=topic, model=model, con=console)

    # Check for due reviews
    review_msg = _check_due_reviews()
    if review_msg:
        console.print(f"[dim]{review_msg}[/dim]")

    while True:
        try:
            from pitagora.cli.repl_input import pitagora_prompt
            user_input = pitagora_prompt(mode, topic)
            
            if not user_input.strip():
                continue

            # Handle commands
            if user_input.strip().startswith("/"):
                cmd_parts = user_input.strip().split(" ", 1)
                cmd = cmd_parts[0].lower()
                arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

                if cmd in ("/quit", "/exit", "/q"):
                    console.print("[dim]Goodbye! Keep reasoning.[/dim]")
                    break
                elif cmd == "/clear":
                    messages = [{"role": "system", "content": system_prompt}]
                    console.print("[dim]Conversation cleared.[/dim]")
                    continue
                elif cmd == "/mode":
                    if arg:
                        mode = arg.strip()
                        console.print(f"[dim]Mode: {mode}[/dim]")
                    continue
                elif cmd == "/topic":
                    if arg:
                        topic = arg.strip()
                        console.print(f"[dim]Topic: {topic}[/dim]")
                    continue
                elif cmd == "/model":
                    if arg:
                        config["default_model"] = arg.strip()
                        model = arg.strip()
                        console.print(f"[dim]Model: {model}[/dim]")
                    continue
                elif cmd == "/verify":
                    if arg:
                        with console.status("[cyan]Verifying...[/cyan]"):
                            from pitagora.math_engine.sandbox import SymPySandbox
                            sandbox = SymPySandbox()
                            result = sandbox.evaluate(arg)
                        if result.verified:
                            console.print(f"[green]✓ {result.value}[/green]")
                            if result.latex:
                                console.print(f"  LaTeX: {result.latex}")
                        else:
                            console.print(f"[red]✗ {result.error}[/red]")
                    continue
                elif cmd == "/research":
                    if arg:
                        with console.status("[cyan]Researching...[/cyan]"):
                            from pitagora.knowledge.acquisition import KnowledgeAcquisition
                            acquirer = KnowledgeAcquisition()
                            result = acquirer.research_topic(arg, depth="shallow")
                        if result.get("findings"):
                            console.print(f"[bold]Found {len(result['findings'])} findings:[/bold]")
                            for f in result["findings"][:5]:
                                console.print(f"  • {f}")
                    continue
                elif cmd == "/save":
                    from pitagora.sessions import save_session
                    sid = save_session(messages, topic=topic, mode=mode)
                    console.print(f"[green]✓ Session saved: {sid}[/green]")
                    continue
                elif cmd == "/sessions":
                    from pitagora.sessions import list_sessions
                    sessions = list_sessions()
                    if not sessions:
                        console.print("[dim]No saved sessions.[/dim]")
                    else:
                        for s in sessions:
                            console.print(f"  [cyan]{s['id']}[/cyan] — {s['topic']} ({s['mode']}) — {s['message_count']} msgs")
                    continue
                elif cmd == "/resume":
                    from pitagora.sessions import list_sessions, load_session
                    if arg:
                        sid = arg.strip()
                    else:
                        sessions = list_sessions(limit=1)
                        sid = sessions[0]["id"] if sessions else None
                    if sid:
                        loaded = load_session(sid)
                        if loaded:
                            messages = loaded
                            console.print(f"[green]✓ Resumed session {sid} ({len(messages)} messages)[/green]")
                        else:
                            console.print(f"[red]Session not found: {sid}[/red]")
                    else:
                        console.print("[dim]No sessions to resume.[/dim]")
                    continue
                elif cmd == "/quiz":
                    quiz_prompt = (
                        f"Generate a practice problem on '{topic}' at intermediate level. "
                        f"Format: state the problem clearly, then say HINTS: followed by hints. "
                        f"Do NOT give the solution."
                    )
                    messages.append({"role": "user", "content": quiz_prompt})
                    with console.status("[cyan]Generating quiz...[/cyan]"):
                        response = chat_completion(messages, model=model, config=config)
                    messages.append({"role": "assistant", "content": response})
                    console.print()
                    console.print(Markdown(response))
                    console.print()
                    continue
                elif cmd == "/progress":
                    try:
                        from pitagora.cli.commands.onboard import load_profile
                        from pitagora.concepts.graph import ConceptGraph
                        from pitagora.memory.user_graph import UserGraph
                        
                        profile = load_profile()
                        cg = ConceptGraph()
                        ug = UserGraph()
                        
                        console.print("[bold]📊 Progress Dashboard[/bold]\n")
                        
                        if profile:
                            console.print(f"Level: {', '.join(f'{k}: {v}' for k, v in profile.get('levels', {}).items())}")
                        
                        console.print(f"Concepts in graph: {len(cg.graph)}")
                        
                        stats = ug.get_user_stats(profile.get("name", "default") if profile else "default")
                        console.print(f"Topics studied: {stats['topics_studied']}")
                        console.print(f"Concepts mastered: {stats['concepts_mastered']}")
                        console.print(f"Total study time: {stats['total_hours']}h")
                        
                        # Knowledge gaps
                        gaps = ug.get_knowledge_gaps(profile.get("name", "default") if profile else "default")
                        if gaps:
                            console.print(f"\n[yellow]Knowledge gaps ({len(gaps)}):[/yellow]")
                            for g in gaps[:5]:
                                console.print(f"  • {g['concept']} (needed for: {g['needed_for']})")
                    except Exception as e:
                        console.print(f"[dim]Progress unavailable: {e}[/dim]")
                    continue
                elif cmd == "/ingest":
                    if arg:
                        from pathlib import Path

                        from pitagora.knowledge.base import KnowledgeBase
                        from pitagora.knowledge.chunker import SmartChunker
                        from pitagora.knowledge.ingester import DocumentIngester
                        
                        target = Path(arg.strip()).expanduser()
                        if target.exists():
                            kb = KnowledgeBase()
                            ingester = DocumentIngester()
                            chunker = SmartChunker()
                            
                            files = list(target.glob("**/*")) if target.is_dir() else [target]
                            from pitagora.core.constants import SUPPORTED_FORMATS
                            exts = set(SUPPORTED_FORMATS) | {".ipynb", ".html"}
                            files = [f for f in files if f.suffix.lower() in exts]
                            
                            count = 0
                            for f in files[:10]:  # Limit to 10 files
                                try:
                                    text = ingester.extract_text(str(f))
                                    if text and len(text) > 50:
                                        chunks = chunker.chunk_text(text, source=str(f))
                                        kb.add_document(str(f), f.stem, topic, chunks=chunks)
                                        count += 1
                                except Exception:
                                    continue
                            console.print(f"[green]✓ Ingested {count}/{len(files)} documents[/green]")
                        else:
                            console.print(f"[red]Path not found: {target}[/red]")
                    else:
                        console.print("[dim]Usage: /ingest <path>[/dim]")
                    continue
                elif cmd == "/explore":
                    from pitagora.teaching.analyzer import ResponseAnalyzer
                    from pitagora.teaching.session import TeachingSession, TeachingState
                    from pitagora.teaching.ui import (
                        show_comprehension_gauge,
                        show_controls,
                        show_topic_overview,
                    )

                    if arg.strip() == "--continue":
                        # Resume the most recent paused/active journey for any topic.
                        try:
                            from pitagora.journeys.store import list_journeys, load_journey
                            journeys = [j for j in list_journeys()
                                         if j.get("status") in ("active", "paused")]
                            if not journeys:
                                console.print("[dim]No journeys to continue. Use /explore <topic>.[/dim]")
                                continue
                            jid = journeys[0]["id"]
                            teaching_journey = load_journey(jid)
                            teaching_session = TeachingSession.from_dict(
                                teaching_journey.session_state
                            )
                            teaching_analyzer = ResponseAnalyzer(chat_completion)
                            topic = teaching_session.topic
                            console.print(
                                f"[green]✓ Resumed journey '{teaching_journey.topic}' "
                                f"({teaching_session.interaction_count} interactions)[/green]"
                            )
                            show_comprehension_gauge(teaching_session.comprehension_score, console)
                            show_controls(console)
                        except Exception as e:
                            console.print(f"[red]Resume failed: {e}[/red]")
                        continue

                    if not arg.strip():
                        console.print("[dim]Usage: /explore <topic>  (or /explore --continue)[/dim]")
                        continue

                    explore_topic = arg.strip()
                    with console.status("[cyan]Designing learning path...[/cyan]"):
                        subs = _generate_sub_concepts(explore_topic, config, model)
                    teaching_session = TeachingSession(
                        topic=explore_topic, sub_concepts=subs, user_level="intermediate",
                    )
                    # WS1: seed the initial style from cross-session metrics when available.
                    _seed_session_style(teaching_session, feedback_improver)
                    teaching_session.transition(TeachingState.exploring)
                    teaching_analyzer = ResponseAnalyzer(chat_completion)
                    topic = explore_topic

                    # Auto-create or resume a journey (TASK 3 wiring).
                    try:
                        from pitagora.journeys.store import get_or_create_journey
                        teaching_journey = get_or_create_journey(explore_topic, subs)
                        teaching_journey.session_state = teaching_session.to_dict()
                    except Exception:
                        teaching_journey = None

                    show_topic_overview(explore_topic, subs, con=console)
                    console.print(
                        "[dim]Teaching mode active. Type a reply, or a shortcut: "
                        "n/e/d/s/?/v/q/p. /help for all commands.[/dim]\n"
                    )
                    # First teaching turn: introduce the first sub-concept.
                    _run_teaching_turn(
                        console, teaching_session, teaching_analyzer,
                        "begin", config, model, messages,
                        improver=feedback_improver, skill_evo=feedback_skill_evo,
                        skills_engine=feedback_skills_engine,
                    )
                    continue
                elif cmd == "/journeys":
                    try:
                        from pitagora.journeys.store import list_journeys
                        journeys = list_journeys()
                        if not journeys:
                            console.print("[dim]No journeys yet. Use /explore <topic>.[/dim]")
                        else:
                            icons = {"active": "🟢", "paused": "⏸", "completed": "✓", "abandoned": "✗"}
                            for j in journeys:
                                icon = icons.get(j.get("status"), "•")
                                console.print(
                                    f"  {icon} [cyan]{j['id']}[/cyan] — {j['topic']} "
                                    f"({j.get('status', '?')}) — {j.get('interaction_count', 0)} interactions"
                                )
                    except Exception as e:
                        console.print(f"[dim]Journeys unavailable: {e}[/dim]")
                    continue
                elif cmd == "/dashboard":
                    try:
                        from pitagora.journeys.store import list_journeys
                        from pitagora.teaching.ui import show_journey_map
                        journeys = list_journeys()
                        if not journeys:
                            console.print("[dim]No journeys yet. Use /explore <topic>.[/dim]")
                        else:
                            for j in journeys:
                                subs = j.get("sub_concepts", [])
                                console.print(f"[bold]{j['topic']}[/bold] ({j.get('status', '?')})")
                                show_journey_map(j["topic"], subs, console)
                    except Exception as e:
                        console.print(f"[dim]Dashboard unavailable: {e}[/dim]")
                    continue
                elif cmd == "/workflow":
                    import asyncio as _asyncio

                    from pitagora.agents.data_analyst import DataAnalystAgent
                    from pitagora.agents.explainer import ExplainerAgent
                    from pitagora.agents.prover import ProverAgent
                    from pitagora.agents.providers import get_provider
                    from pitagora.agents.providers.base import ProviderConfig
                    from pitagora.agents.researcher import ResearchAgent
                    from pitagora.agents.reviewer import ReviewerAgent
                    from pitagora.agents.self_improver import SelfImproverAgent
                    from pitagora.agents.tutor import TutorAgent
                    from pitagora.agents.visualizer import VisualizerAgent
                    from pitagora.agents.workflows import WorkflowEngine

                    AVAILABLE_WORKFLOWS = (
                        "teach", "derive_and_prove", "concept_mastery",
                        "debate", "deep_research", "philosophical_reasoning",
                    )
                    parts = arg.strip().split(" ", 1)
                    wf_name = parts[0] if parts else ""
                    wf_arg = parts[1] if len(parts) > 1 else ""
                    if not wf_name or wf_name not in AVAILABLE_WORKFLOWS:
                        console.print(
                            f"[red]Usage: /workflow <name> <args...>[/red]\n"
                            f"[dim]Workflows: {', '.join(AVAILABLE_WORKFLOWS)}[/dim]"
                        )
                        continue
                    try:
                        prov_cfg = ProviderConfig(
                            api_key=config.get("api_key", DEFAULT_API_KEY),
                            model=model,
                            base_url=config.get("base_url", DEFAULT_BASE_URL),
                            max_tokens=4096,
                        )
                        prov = get_provider("openai", prov_cfg)
                        agents = {
                            "tutor": TutorAgent(prov),
                            "researcher": ResearchAgent(prov),
                            "prover": ProverAgent(prov),
                            "reviewer": ReviewerAgent(prov),
                            "visualizer": VisualizerAgent(prov),
                            "explainer": ExplainerAgent(prov),
                            "self_improver": SelfImproverAgent(prov),
                            "data_analyst": DataAnalystAgent(prov),
                            "debate": TutorAgent(prov),  # ponytail: debate agent reused; add DebateAgent if workflow needs its specific methods
                        }
                        engine = WorkflowEngine(agents=agents)
                        inputs = {"topic": wf_arg or topic, "level": "intermediate"}
                        with console.status(f"[cyan]Running workflow '{wf_name}'...[/cyan]"):
                            result = _asyncio.run(engine.execute(inputs, workflow_name_or_def=wf_name))
                        final = result.get("final_output") or ""
                        console.print()
                        console.print(Markdown(final or "(no output)"))
                        console.print()
                    except Exception as e:
                        console.print(f"[red]Workflow failed: {e}[/red]")
                    continue
                elif cmd == "/latex":
                    if arg:
                        from pitagora.latex_render import render_equation_box
                        console.print(render_equation_box(arg))
                    continue
                elif cmd == "/rate":
                    # WS1: explicit feedback for free-form chat (no automated
                    # classifier signal there). Rates the last free-form response
                    # 1-5 and records it in the self-improving feedback loop.
                    if feedback_improver is None:
                        console.print("[dim]Feedback loop unavailable.[/dim]")
                        continue
                    try:
                        q = int(arg.strip()) if arg.strip() else 0
                    except ValueError:
                        q = 0
                    if not 1 <= q <= 5:
                        console.print("[dim]Usage: /rate <1-5>  (rates the last response)[/dim]")
                        continue
                    try:
                        feedback_improver.record_interaction(
                            topic=last_freeform.get("topic", topic),
                            level="intermediate",
                            strategy_used=last_freeform.get("strategy", "socratic"),
                            response_quality=q,
                        )
                        console.print(f"[green]✓ Recorded rating {q}/5.[/green]")
                    except Exception as e:
                        console.print(f"[red]Rating failed: {e}[/red]")
                    continue
                elif cmd == "/help":
                    console.print(Panel(
                        "[bold]Chat Commands:[/bold]\n"
                        "  /mode <mode>      Switch mode (study/explore/reason/verify)\n"
                        "  /topic <name>     Change topic\n"
                        "  /model <name>     Change model\n"
                        "  /explore <topic>  Start a guided teaching session\n"
                        "  /explore --continue  Resume the latest journey\n"
                        "  /journeys         List saved learning journeys\n"
                        "  /dashboard        Visual journey overview\n"
                        "  /workflow <name> <args>  Run a multi-agent workflow\n"
                        "                    (teach, derive_and_prove, concept_mastery,\n"
                        "                     debate, deep_research, philosophical_reasoning)\n"
                        "  /verify <expr>    Verify math with SymPy\n"
                        "  /latex <expr>     Render LaTeX as Unicode\n"
                        "  /quiz             Generate a practice problem\n"
                        "  /progress         Show learning progress dashboard\n"
                        "  /research <q>     Web research\n"
                        "  /ingest <path>    Ingest documents into knowledge base\n"
                        "  /save             Save current session\n"
                        "  /sessions         List saved sessions\n"
                        "  /resume [id]      Resume a saved session\n"
                        "  /rate <1-5>       Rate the last response (feeds the feedback loop)\n"
                        "  /clear            Clear conversation\n"
                        "  /quit             Exit\n\n"
                        "[bold]Teaching shortcuts (in teaching mode):[/bold]\n"
                        "  n=next  e=explain differently  d=go deeper  s=skip\n"
                        "  ?=confused  v=visualize  q=quiz  p=pause\n\n"
                        "[bold]CLI Commands:[/bold]\n"
                        "  pitagora setup      Configure providers\n"
                        "  pitagora onboard     Set up learning profile\n"
                        "  pitagora doctor      System health check\n"
                        "  pitagora review      Spaced repetition\n"
                        "  pitagora profile     View knowledge map\n",
                        title="Help",
                        border_style="cyan",
                    ))
                    continue
                else:
                    console.print(f"[dim]Unknown: {cmd}. /help for commands.[/dim]")
                    continue

            # ─── MAIN CHAT FLOW ───

            # Teaching mode: route every reply through the analyzer + session.
            if teaching_session is not None:
                # Pause shortcut exits teaching back to free-form (session saved).
                if user_input.strip().lower() == "p":
                    teaching_session.pause()
                    if teaching_journey is not None:
                        try:
                            from pitagora.journeys.store import save_journey
                            teaching_journey.session_state = teaching_session.to_dict()
                            save_journey(teaching_journey)
                        except Exception:
                            pass
                    console.print(
                        "[dim]Teaching paused. Resumable with /explore --continue. "
                        "Back to free-form chat.[/dim]"
                    )
                    teaching_session = None
                    teaching_analyzer = None
                    continue
                response = _run_teaching_turn(
                    console, teaching_session, teaching_analyzer,
                    user_input, config, model, messages,
                    improver=feedback_improver, skill_evo=feedback_skill_evo,
                    skills_engine=feedback_skills_engine,
                )
                # Auto-save journey after each teaching turn.
                if teaching_journey is not None:
                    try:
                        from pitagora.journeys.store import save_journey
                        teaching_journey.session_state = teaching_session.to_dict()
                        teaching_journey.comprehension_history.append(
                            teaching_session.comprehension_score
                        )
                        teaching_journey.sub_concepts = [
                            sc.to_dict() for sc in teaching_session.sub_concepts
                        ]
                        teaching_journey.interaction_count = teaching_session.interaction_count
                        save_journey(teaching_journey)
                    except Exception:
                        pass
                # If the session completed, drop back to free-form chat.
                from pitagora.teaching.session import TeachingState as _TS
                if teaching_session.state == _TS.completed:
                    from pitagora.teaching.ui import show_session_summary
                    mastered = [
                        sc.name for sc in teaching_session.sub_concepts
                        if sc.mastery >= 0.8
                    ]
                    show_session_summary(
                        teaching_session.topic,
                        teaching_session.comprehension_score,
                        teaching_session.interaction_count,
                        teaching_session.style_effectiveness.best(),
                        mastered,
                        console,
                    )
                    teaching_session = None
                    teaching_analyzer = None
                continue

            # 1. RAG: Retrieve relevant context from knowledge base
            rag_ctx = _get_rag_context(user_input)
            concept_ctx = _get_concept_context(topic)
            
            # 2. Build enriched prompt
            enriched = user_input
            if rag_ctx or concept_ctx:
                context_parts = []
                if rag_ctx:
                    context_parts.append(rag_ctx)
                if concept_ctx:
                    context_parts.append(concept_ctx)
                enriched = "\n\n".join(context_parts) + f"\n\nUser question: {user_input}"

            messages.append({"role": "user", "content": enriched})

            # 3. Get response
            with console.status("[bold cyan]Thinking...[/bold cyan]"):
                response = chat_completion(messages, model=model, config=config)

            messages.append({"role": "assistant", "content": response})

            # 4. Display response
            console.print()
            console.print(Markdown(response))

            # 5. SymPy verification of equations in response
            verification = _verify_math(response)
            if verification:
                console.print(f"\n[dim]{verification}[/dim]")

            # 6. Save to memory
            _save_to_memory("user", user_input, topic=topic)
            _save_to_memory("assistant", response, topic=topic)

            # 7. Record study activity
            _record_study(topic, user_input)

            # Track context for the /rate command (free-form feedback loop).
            last_freeform = {"topic": topic, "strategy": "socratic"}

            console.print()

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            continue
        except KeyboardInterrupt:
            console.print("\n[dim]Use /quit to exit.[/dim]")
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break
