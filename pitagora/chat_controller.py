"""Shared headless chat controller.

The :class:`ChatController` is a pure state machine that drives a Pitagora
conversation. It owns the message list and session metadata and emits
:class:`ChatEvent` objects to its caller (the TUI, a CLI, or a test). All
external dependencies — completion, RAG, memory, spaced repetition — are
injected as callables so the controller never performs I/O of its own when
deps are supplied.

This module delegates to the helpers already living in :mod:`pitagora.chat`
so the existing runtime behaviour is preserved when callers do not inject
their own dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterator, Optional

from pitagora import chat as chat_runtime


@dataclass(frozen=True)
class ChatEvent:
    """A single emitted conversation event.

    ``kind`` is a small string tag the consumer switches on (``"user"``,
    ``"status"``, ``"markdown"``, ``"state_changed"``, ``"error"`` ...).
    ``content`` carries the payload appropriate to the kind and ``metadata``
    holds optional structured flags.
    """

    kind: str
    content: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChatController:
    """Headless conversation controller.

    The controller is intentionally framework-agnostic: it knows nothing
    about Textual, Rich, or the terminal. It produces a stream of
    :class:`ChatEvent` values from :meth:`handle_input` and exposes a
    :attr:`context` snapshot for status bars.
    """

    COMMANDS = {
        "/mode": "_cmd_mode",
        "/topic": "_cmd_topic",
        "/model": "_cmd_model",
        "/explore": "_cmd_explore",
        "/verify": "_cmd_verify",
        "/research": "_cmd_research",
        "/save": "_cmd_save",
        "/sessions": "_cmd_sessions",
        "/resume": "_cmd_resume",
        "/quiz": "_cmd_quiz",
        "/progress": "_cmd_progress",
        "/ingest": "_cmd_ingest",
        "/journeys": "_cmd_journeys",
        "/dashboard": "_cmd_dashboard",
        "/workflow": "_cmd_workflow",
        "/latex": "_cmd_latex",
        "/rate": "_cmd_rate",
        "/help": "_cmd_help",
        "/clear": "_cmd_clear",
        "/quit": "_cmd_quit",
        "/exit": "_cmd_quit",
        "/q": "_cmd_quit",
    }

    def __init__(
        self,
        mode: str = "study",
        topic: str = "general",
        system_prompt: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
        completion: Optional[Callable[..., str]] = None,
        rag_lookup: Optional[Callable[[str], str]] = None,
        concept_lookup: Optional[Callable[[str], str]] = None,
        verify_math: Optional[Callable[[str], Optional[str]]] = None,
        save_memory: Optional[Callable[..., None]] = None,
        record_study: Optional[Callable[..., None]] = None,
        due_reviews: Optional[Callable[[], Optional[str]]] = None,
        user_context: Optional[str] = None,
        feedback_loop: Optional[tuple[Any, Any, Any]] = None,
    ) -> None:
        self.mode = mode
        self.topic = topic
        self.config = config or chat_runtime.load_provider_config()
        self.model = self.config.get("default_model", "unknown")
        self.completion = completion or chat_runtime.chat_completion
        self.rag_lookup = rag_lookup or chat_runtime._get_rag_context
        self.concept_lookup = concept_lookup or chat_runtime._get_concept_context
        self.verify_math = verify_math or chat_runtime._verify_math
        self.save_memory = save_memory or chat_runtime._save_to_memory
        self.record_study = record_study or chat_runtime._record_study
        self.due_reviews = due_reviews or chat_runtime._check_due_reviews
        self.started_at = datetime.now()
        self.message_count = 0
        self.teaching_session = None
        self.teaching_analyzer = None
        self.teaching_journey = None
        self.last_freeform = {"topic": topic, "strategy": "socratic"}
        self.system_prompt = system_prompt or self._default_system_prompt()
        context_text = (
            chat_runtime._get_user_context()
            if user_context is None
            else user_context
        )
        if context_text:
            self.system_prompt += f"\n\n{context_text}"
        self.messages = [{"role": "system", "content": self.system_prompt}]
        loop = (
            chat_runtime._build_feedback_loop()
            if feedback_loop is None
            else feedback_loop
        )
        (
            self.feedback_improver,
            self.feedback_skill_evo,
            self.feedback_skills_engine,
        ) = loop

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are Pitagora, an expert mathematics and physics tutor. "
            "You explain concepts clearly using the Socratic method: ask guiding "
            "questions before giving answers. Use LaTeX notation for equations "
            "($..$ inline, $$...$$ display). Be precise, rigorous, and encouraging. "
            "When a student makes a mistake, guide them to discover the error rather "
            "than just correcting it. Use markdown formatting for structure."
        )

    @property
    def context(self) -> dict[str, Any]:
        """Snapshot of session state for status display."""
        session = self.teaching_session
        return {
            "mode": self.mode,
            "topic": self.topic,
            "model": self.model,
            "message_count": self.message_count,
            "elapsed_seconds": int((datetime.now() - self.started_at).total_seconds()),
            "teaching": session is not None,
            "comprehension": session.comprehension_score if session else 0.0,
            "sub_concepts": (
                [item.to_dict() for item in session.sub_concepts] if session else []
            ),
            "journey": getattr(self.teaching_journey, "topic", None),
            "journey_progress": (
                (session.current_index + 1) / len(session.sub_concepts)
                if session and session.sub_concepts
                else 0.0
            ),
            "due_reviews": self.due_reviews(),
        }

    def handle_input(self, user_input: str) -> Iterator[ChatEvent]:
        """Dispatch a line of user input to the appropriate handler.

        Empty/whitespace input yields nothing. Lines starting with ``/`` are
        treated as commands. An active teaching session routes to the teaching
        handler. Otherwise the free-form study turn runs.
        """
        text = user_input.strip()
        if not text:
            return
        if text.startswith("/"):
            yield from self._handle_command(text)
            return
        if self.teaching_session is not None:
            yield from self._handle_teaching_turn(text)
            return
        yield from self._handle_freeform_turn(user_input)

    def _handle_freeform_turn(self, user_input: str) -> Iterator[ChatEvent]:
        yield ChatEvent("user", user_input)
        rag_context = self.rag_lookup(user_input)
        concept_context = self.concept_lookup(self.topic)
        contexts = [value for value in (rag_context, concept_context) if value]
        enriched = (
            "\n\n".join(contexts) + f"\n\nUser question: {user_input}"
            if contexts
            else user_input
        )
        self.messages.append({"role": "user", "content": enriched})
        yield ChatEvent("status", "Thinking...", {"busy": True})
        try:
            response = self.completion(
                self.messages,
                model=self.model,
                config=self.config,
            )
        except Exception:
            # Roll back the user message so retries leave the conversation
            # in a consistent state (no orphan user turn without a reply).
            self.messages.pop()
            raise
        self.messages.append({"role": "assistant", "content": response})
        yield ChatEvent("markdown", response)
        verification = self.verify_math(response)
        if verification:
            yield ChatEvent("status", verification, {"verification": True})
        self.save_memory("user", user_input, topic=self.topic)
        self.save_memory("assistant", response, topic=self.topic)
        self.record_study(self.topic, user_input)
        self.message_count += 1
        self.last_freeform = {"topic": self.topic, "strategy": "socratic"}
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def _handle_command(self, text: str) -> Iterator[ChatEvent]:
        command, _, argument = text.partition(" ")
        command = command.lower()
        handler_name = self.COMMANDS.get(command)
        if handler_name is None:
            yield ChatEvent("error", f"Unknown: {command}. /help for commands.")
            return
        yield from getattr(self, handler_name)(argument.strip())

    # ─── Direct state-change commands ───

    def _cmd_mode(self, argument: str) -> Iterator[ChatEvent]:
        if not argument:
            yield ChatEvent("status", f"Current mode: {self.mode}")
            return
        self.mode = argument
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def _cmd_topic(self, argument: str) -> Iterator[ChatEvent]:
        if not argument:
            yield ChatEvent("status", f"Current topic: {self.topic}")
            return
        self.topic = argument
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def _cmd_model(self, argument: str) -> Iterator[ChatEvent]:
        if not argument:
            yield ChatEvent("status", f"Current model: {self.model}")
            return
        self.config["default_model"] = argument
        self.model = argument
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def _cmd_clear(self, argument: str) -> Iterator[ChatEvent]:
        self.messages = [{"role": "system", "content": self.system_prompt}]
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def _cmd_quit(self, argument: str) -> Iterator[ChatEvent]:
        yield ChatEvent("status", "Goodbye!", metadata={"quit": True})

    # ─── Session commands ───

    def _cmd_save(self, argument: str) -> Iterator[ChatEvent]:
        from pitagora.sessions import save_session
        sid = save_session(self.messages, topic=self.topic, mode=self.mode)
        yield ChatEvent("status", f"✓ Session saved: {sid}")
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def _cmd_sessions(self, argument: str) -> Iterator[ChatEvent]:
        from pitagora.sessions import list_sessions
        sessions = list_sessions()
        if not sessions:
            yield ChatEvent("status", "No saved sessions.")
            return
        lines = [
            f"  {s['id']} — {s['topic']} ({s['mode']}) — {s['message_count']} msgs"
            for s in sessions
        ]
        yield ChatEvent("markdown", "\n".join(lines))

    def _cmd_resume(self, argument: str) -> Iterator[ChatEvent]:
        from pitagora.sessions import load_session, list_sessions
        if argument:
            sid = argument
        else:
            sessions = list_sessions(limit=1)
            sid = sessions[0]["id"] if sessions else None
        if sid:
            loaded = load_session(sid)
            if loaded:
                self.messages = loaded
                yield ChatEvent(
                    "status", f"✓ Resumed session {sid} ({len(loaded)} messages)"
                )
            else:
                yield ChatEvent("error", f"Session not found: {sid}")
        else:
            yield ChatEvent("status", "No sessions to resume.")
        yield ChatEvent("state_changed", metadata={"context": self.context})

    # ─── Rendering commands ───

    def _cmd_latex(self, argument: str) -> Iterator[ChatEvent]:
        if not argument:
            yield ChatEvent("status", "Usage: /latex <expr>")
            return
        from pitagora.latex_render import render_equation_box
        yield ChatEvent("renderable", render_equation_box(argument))

    def _cmd_help(self, argument: str) -> Iterator[ChatEvent]:
        from rich.panel import Panel
        yield ChatEvent(
            "renderable",
            Panel(
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
            ),
        )

    # ─── Feedback command ───

    def _cmd_rate(self, argument: str) -> Iterator[ChatEvent]:
        if self.feedback_improver is None:
            yield ChatEvent("status", "Feedback loop unavailable.")
            return
        try:
            q = int(argument) if argument else 0
        except ValueError:
            q = 0
        if not 1 <= q <= 5:
            yield ChatEvent("status", "Usage: /rate <1-5>  (rates the last response)")
            return
        try:
            self.feedback_improver.record_interaction(
                topic=self.last_freeform.get("topic", self.topic),
                level="intermediate",
                strategy_used=self.last_freeform.get("strategy", "socratic"),
                response_quality=q,
            )
            yield ChatEvent("status", f"✓ Recorded rating {q}/5.")
        except Exception as e:
            yield ChatEvent("error", f"Rating failed: {e}")

    # ─── Math / knowledge commands ───

    def _cmd_verify(self, argument: str) -> Iterator[ChatEvent]:
        if not argument:
            yield ChatEvent("status", "Usage: /verify <expr>")
            return
        yield ChatEvent("status", "Verifying...", {"busy": True})
        from pitagora.math_engine.sandbox import SymPySandbox
        sandbox = SymPySandbox()
        result = sandbox.evaluate(argument)
        if result.verified:
            text = f"✓ {result.value}"
            if result.latex:
                text += f"\n  LaTeX: {result.latex}"
            yield ChatEvent("status", text, {"verification": True})
        else:
            yield ChatEvent("error", f"✗ {result.error}")

    def _cmd_research(self, argument: str) -> Iterator[ChatEvent]:
        if not argument:
            yield ChatEvent("status", "Usage: /research <query>")
            return
        yield ChatEvent("status", "Researching...", {"busy": True})
        from pitagora.knowledge.acquisition import KnowledgeAcquisition
        acquirer = KnowledgeAcquisition()
        result = acquirer.research_topic(argument, depth="shallow")
        findings = result.get("findings", [])
        if findings:
            lines = [f"Found {len(findings)} findings:"]
            for f in findings[:5]:
                lines.append(f"  • {f}")
            yield ChatEvent("markdown", "\n".join(lines))
        else:
            yield ChatEvent("status", "No findings.")

    def _cmd_quiz(self, argument: str) -> Iterator[ChatEvent]:
        quiz_prompt = (
            f"Generate a practice problem on '{self.topic}' at intermediate level. "
            f"Format: state the problem clearly, then say HINTS: followed by hints. "
            f"Do NOT give the solution."
        )
        self.messages.append({"role": "user", "content": quiz_prompt})
        yield ChatEvent("status", "Generating quiz...", {"busy": True})
        response = self.completion(self.messages, model=self.model, config=self.config)
        self.messages.append({"role": "assistant", "content": response})
        yield ChatEvent("markdown", response)
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def _cmd_progress(self, argument: str) -> Iterator[ChatEvent]:
        try:
            from pitagora.concepts.graph import ConceptGraph
            from pitagora.memory.user_graph import UserGraph
            from pitagora.cli.commands.onboard import load_profile

            profile = load_profile()
            cg = ConceptGraph()
            ug = UserGraph()
            name = profile.get("name", "default") if profile else "default"

            lines = ["📊 Progress Dashboard\n"]
            if profile:
                levels = ", ".join(
                    f"{k}: {v}" for k, v in profile.get("levels", {}).items()
                )
                if levels:
                    lines.append(f"Level: {levels}")
            lines.append(f"Concepts in graph: {len(cg.graph)}")
            stats = ug.get_user_stats(name)
            lines.append(f"Topics studied: {stats['topics_studied']}")
            lines.append(f"Concepts mastered: {stats['concepts_mastered']}")
            lines.append(f"Total study time: {stats['total_hours']}h")
            gaps = ug.get_knowledge_gaps(name)
            if gaps:
                lines.append(f"\nKnowledge gaps ({len(gaps)}):")
                for g in gaps[:5]:
                    lines.append(f"  • {g['concept']} (needed for: {g['needed_for']})")
            yield ChatEvent("markdown", "\n".join(lines))
        except Exception as e:
            yield ChatEvent("status", f"Progress unavailable: {e}")

    def _cmd_ingest(self, argument: str) -> Iterator[ChatEvent]:
        if not argument:
            yield ChatEvent("status", "Usage: /ingest <path>")
            return
        from pathlib import Path
        target = Path(argument).expanduser()
        if not target.exists():
            yield ChatEvent("error", f"Path not found: {target}")
            return
        yield ChatEvent("status", "Ingesting...", {"busy": True})
        from pitagora.knowledge.base import KnowledgeBase
        from pitagora.knowledge.ingester import DocumentIngester
        from pitagora.knowledge.chunker import SmartChunker
        from pitagora.core.constants import SUPPORTED_FORMATS

        kb = KnowledgeBase()
        ingester = DocumentIngester()
        chunker = SmartChunker()
        files = list(target.glob("**/*")) if target.is_dir() else [target]
        exts = set(SUPPORTED_FORMATS) | {".ipynb", ".html"}
        files = [f for f in files if f.suffix.lower() in exts]
        count = 0
        for f in files[:10]:
            try:
                text = ingester.extract_text(str(f))
                if text and len(text) > 50:
                    chunks = chunker.chunk_text(text, source=str(f))
                    kb.add_document(str(f), f.stem, self.topic, chunks=chunks)
                    count += 1
            except Exception:
                continue
        yield ChatEvent("status", f"✓ Ingested {count}/{len(files)} documents")

    # ─── Journey commands ───

    def _cmd_journeys(self, argument: str) -> Iterator[ChatEvent]:
        try:
            from pitagora.journeys.store import list_journeys
            journeys = list_journeys()
            if not journeys:
                yield ChatEvent("status", "No journeys yet. Use /explore <topic>.")
                return
            icons = {"active": "🟢", "paused": "⏸", "completed": "✓", "abandoned": "✗"}
            lines = []
            for j in journeys:
                icon = icons.get(j.get("status"), "•")
                lines.append(
                    f"  {icon} {j['id']} — {j['topic']} ({j.get('status', '?')}) "
                    f"— {j.get('interaction_count', 0)} interactions"
                )
            yield ChatEvent("markdown", "\n".join(lines))
        except Exception as e:
            yield ChatEvent("status", f"Journeys unavailable: {e}")

    def _cmd_dashboard(self, argument: str) -> Iterator[ChatEvent]:
        try:
            from io import StringIO
            from rich.console import Console
            from pitagora.journeys.store import list_journeys
            from pitagora.teaching.ui import show_journey_map
            journeys = list_journeys()
            if not journeys:
                yield ChatEvent("status", "No journeys yet. Use /explore <topic>.")
                return
            buf = StringIO()
            console = Console(file=buf, force_terminal=False, width=80)
            for j in journeys:
                subs = j.get("sub_concepts", [])
                console.print(f"[bold]{j['topic']}[/bold] ({j.get('status', '?')})")
                show_journey_map(j["topic"], subs, console)
            yield ChatEvent("markdown", buf.getvalue().rstrip())
        except Exception as e:
            yield ChatEvent("status", f"Dashboard unavailable: {e}")

    def _cmd_workflow(self, argument: str) -> Iterator[ChatEvent]:
        import asyncio as _asyncio
        from pitagora.agents.providers.base import ProviderConfig
        from pitagora.agents.providers import get_provider
        from pitagora.agents.tutor import TutorAgent
        from pitagora.agents.researcher import ResearchAgent
        from pitagora.agents.prover import ProverAgent
        from pitagora.agents.reviewer import ReviewerAgent
        from pitagora.agents.visualizer import VisualizerAgent
        from pitagora.agents.explainer import ExplainerAgent
        from pitagora.agents.self_improver import SelfImproverAgent
        from pitagora.agents.data_analyst import DataAnalystAgent
        from pitagora.agents.workflows import WorkflowEngine
        from pitagora.core.constants import DEFAULT_API_KEY, DEFAULT_BASE_URL

        AVAILABLE_WORKFLOWS = (
            "teach", "derive_and_prove", "concept_mastery",
            "debate", "deep_research", "philosophical_reasoning",
        )
        parts = argument.split(" ", 1)
        wf_name = parts[0] if parts else ""
        wf_arg = parts[1] if len(parts) > 1 else ""
        if not wf_name or wf_name not in AVAILABLE_WORKFLOWS:
            yield ChatEvent(
                "error",
                f"Usage: /workflow <name> <args...>\n"
                f"Workflows: {', '.join(AVAILABLE_WORKFLOWS)}",
            )
            return
        try:
            prov_cfg = ProviderConfig(
                api_key=self.config.get("api_key", DEFAULT_API_KEY),
                model=self.model,
                base_url=self.config.get("base_url", DEFAULT_BASE_URL),
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
                "debate": TutorAgent(prov),
            }
            engine = WorkflowEngine(agents=agents)
            inputs = {"topic": wf_arg or self.topic, "level": "intermediate"}
            yield ChatEvent("status", f"Running workflow '{wf_name}'...", {"busy": True})
            result = _asyncio.run(engine.execute(inputs, workflow_name_or_def=wf_name))
            final = result.get("final_output") or "(no output)"
            yield ChatEvent("markdown", final)
        except Exception as e:
            yield ChatEvent("error", f"Workflow failed: {e}")

    # ─── Teaching command (stub — full flow in Task 5) ───

    def _cmd_explore(self, argument: str) -> Iterator[ChatEvent]:
        yield ChatEvent(
            "status",
            "Teaching mode is coming in Task 5. Use /help for available commands.",
        )

    def _handle_teaching_turn(self, text: str) -> Iterator[ChatEvent]:
        yield ChatEvent("error", "Teaching mode is not initialized.")
