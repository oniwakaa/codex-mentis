"""Interactive chat REPL — runtime helpers and launch_chat."""

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


_STRATEGY_TO_STYLE = {
    "socratic": "socratic",
    "feynman": "feynman",
    "formal_proof": "formal",
    "analogy": "feynman",
    "side_by_side": "feynman",
}


def _seed_session_style(session, improver) -> None:
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
    try:
        from pitagora.concepts.graph import ConceptGraph

        cg = ConceptGraph()

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


def _get_memory_context(query: str, topic: str = "general", max_entries: int = 3) -> str:
    """Retrieve relevant episodic memories from past sessions for cross-session continuity."""
    try:
        from pitagora.memory.store import MemoryStore

        store = MemoryStore()
        # Search relevant memory entries by query embedding / similarity
        results = store.retrieve(query, top_k=max_entries)
        if not results:
            # Fallback to recent entries for this topic
            history = store.get_topic_history(topic)
            if history:
                results = history[-max_entries:]

        if not results:
            return ""

        context_parts = ["[Relevant memory from previous conversations:]"]
        for r in results:
            content = r.get("content", "")
            if content and (r.get("score") is None or r.get("score", 0.0) >= 0.1):
                context_parts.append(f"- {content}")

        if len(context_parts) > 1:
            return "\n".join(context_parts)
    except Exception as e:
        log.debug("failed to retrieve memory context: %s", e)
    return ""


def _get_user_context() -> str:
    """Get user profile context — level, mastery, recent activity, and persistent memory summary."""
    try:
        from pitagora.cli.commands.onboard import load_profile

        profile = load_profile()
        parts = []
        if profile:
            parts.append(f"[User profile: {profile.get('name', 'Student')}]")
            levels = profile.get("levels", {})
            for subj, level in levels.items():
                parts.append(f"  {subj}: {level}")

            interests = profile.get("interests", [])
            if interests:
                parts.append(f"  Interests: {', '.join(interests)}")

        # Include recent episodic memories summary if available
        try:
            from pitagora.memory.store import MemoryStore

            store = MemoryStore()
            recent_memories = store.list_memories()
            if recent_memories:
                recent_topics = list({m.topic for m in recent_memories[-10:] if m.topic})
                if recent_topics:
                    parts.append(f"  Recent topics studied: {', '.join(recent_topics[:5])}")
        except Exception:
            pass

        return "\n".join(parts)
    except Exception:
        return ""



def _verify_math(response: str) -> str | None:
    import logging
    import re

    log = logging.getLogger(__name__)

    equations = re.findall(r"\$([^$]+)\$", response)
    if not equations:
        return None

    try:
        from pitagora.math_engine.sandbox import SymPySandbox

        sandbox = SymPySandbox()
    except Exception as e:
        log.warning("SymPy sandbox unavailable for verification: %s", e)
        return None

    verified = []
    for eq in equations[:3]:
        try:
            result = sandbox.evaluate(eq)
            if result.verified:
                verified.append(f"  ✓ {eq} = {result.value}")
            elif result.error:
                verified.append(f"  ⚠ {eq}: {result.error}")
        except Exception as e:
            log.warning("verification failed for '%s': %s", eq, e)
            verified.append(f"  ⚠ {eq}: verification error")
    if verified:
        return "[SymPy verification:]\n" + "\n".join(verified)
    return None


def _save_to_memory(role: str, content: str, topic: str = "general") -> None:
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
    try:
        from pitagora.memory.spaced_repetition import SpacedRepetition

        sr = SpacedRepetition()
        due = sr.get_due_reviews()
        if due and len(due) > 0:
            return f"📚 You have {len(due)} concepts due for review. Run `pitagora review start`."
    except Exception as e:
        log.debug("failed to check due reviews: %s", e)
    return None


SUBCONCEPT_GEN_PROMPT = (
    "You are a curriculum designer. Break the given topic into 3 to 6 ordered "
    "sub-concepts that a learner should cover, from foundational to advanced. "
    'Return ONLY a JSON object: {"sub_concepts": ["name1", "name2", ...]}. '
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
    return [f"Foundations of {topic}", f"Core ideas of {topic}", f"Applications of {topic}"]


def _build_teaching_prompt(session, action: str, style: str) -> str:
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


def _render_rich_event(console, event) -> bool:
    from rich.markdown import Markdown

    if event.kind == "markdown":
        console.print(Markdown(str(event.content)))
    elif event.kind == "renderable":
        content = event.content
        if isinstance(content, dict) and content.get("summary"):
            from pitagora.teaching.ui import show_session_summary

            show_session_summary(
                content["topic"],
                content["comprehension"],
                content["interaction_count"],
                content["best_style"],
                content["mastered"],
                console,
            )
        elif isinstance(content, dict) and "sub_concepts" in content:
            from pitagora.teaching.ui import show_topic_overview

            show_topic_overview(
                content["topic"],
                content["sub_concepts"],
                level=content.get("level", "intermediate"),
                con=console,
            )
            console.print(
                "[dim]Teaching mode active. Type a reply, or a shortcut: "
                "n/e/d/s/?/v/q/p. /help for all commands.[/dim]\n"
            )
        else:
            console.print(content)
    elif event.kind == "error":
        console.print(f"[red]{event.content}[/red]")
    elif event.kind == "comprehension":
        from pitagora.teaching.ui import show_comprehension_gauge

        show_comprehension_gauge(float(event.content), console)
    elif event.kind == "subconcepts":
        from pitagora.teaching.ui import show_subconcept_progress

        show_subconcept_progress(
            event.content,
            event.metadata["current_index"],
            console,
        )
    elif event.kind == "controls":
        from pitagora.teaching.ui import show_controls

        show_controls(console)
    elif event.kind == "status" and not event.metadata.get("busy"):
        console.print(f"[dim]{event.content}[/dim]")
    return bool(event.metadata.get("quit"))


def _dispatch_rich_events(console, controller, user_input: str) -> bool:
    status_ctx = None
    quit_requested = False
    try:
        for event in controller.handle_input(user_input):
            if status_ctx is not None:
                status_ctx.__exit__(None, None, None)
                status_ctx = None
            if event.kind == "status" and event.metadata.get("busy"):
                status_ctx = console.status(f"[bold cyan]{event.content}[/bold cyan]")
                status_ctx.__enter__()
                continue
            if _render_rich_event(console, event):
                quit_requested = True
                break
    finally:
        if status_ctx is not None:
            status_ctx.__exit__(None, None, None)
    return quit_requested


def launch_chat(
    mode: str = "study",
    topic: str = "general",
    system_prompt: str | None = None,
    *,
    controller=None,
    input_reader=None,
    con=None,
) -> None:
    from rich.console import Console

    console = con if con is not None else Console()

    if controller is None:
        from pitagora.chat.controller import ChatController

        controller = ChatController(
            mode=mode,
            topic=topic,
            system_prompt=system_prompt,
        )

    if input_reader is None:
        from pitagora.cli.repl_input import pitagora_prompt

        input_reader = pitagora_prompt

    startup = getattr(controller, "startup_events", None)
    if startup is not None:
        for event in startup():
            _render_rich_event(console, event)
    else:
        from pitagora.cli.rich_ui import show_welcome

        show_welcome(
            mode=controller.mode,
            topic=controller.topic,
            model=controller.model,
            con=console,
        )
        review_msg = controller.due_reviews()
        if review_msg:
            console.print(f"[dim]{review_msg}[/dim]")

    while True:
        try:
            user_input = input_reader(controller.mode, controller.topic)
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input or not user_input.strip():
            continue

        try:
            if _dispatch_rich_events(console, controller, user_input):
                break
        except KeyboardInterrupt:
            console.print("\n[dim]Use /quit to exit.[/dim]")
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            continue
