"""UI callback and rendering hooks for chat session."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pitagora.chat.session import ChatSessionState

from pitagora.chat.session import ChatEvent


class ChatRenderer:
    """Renders formatted panels, LaTeX, progress dashboards, and external tools."""

    @staticmethod
    def cmd_latex(argument: str):
        if not argument:
            yield ChatEvent("status", "Usage: /latex <expr>")
            return
        from pitagora.latex_render import render_equation_box

        yield ChatEvent("renderable", render_equation_box(argument))

    @staticmethod
    def cmd_help(argument: str):
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

    @staticmethod
    def cmd_rate(state: ChatSessionState, argument: str):
        if state.feedback_improver is None:
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
            state.feedback_improver.record_interaction(
                topic=state.last_freeform.get("topic", state.topic),
                level="intermediate",
                strategy_used=state.last_freeform.get("strategy", "socratic"),
                response_quality=q,
            )
            yield ChatEvent("status", f"✓ Recorded rating {q}/5.")
        except Exception as e:
            yield ChatEvent("error", f"Rating failed: {e}")

    @staticmethod
    def cmd_verify(argument: str):
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

    @staticmethod
    def cmd_research(argument: str):
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

    @staticmethod
    def cmd_progress(topic: str, argument: str):
        try:
            from pitagora.cli.commands.onboard import load_profile
            from pitagora.concepts.graph import ConceptGraph
            from pitagora.memory.user_graph import UserGraph

            profile = load_profile()
            cg = ConceptGraph()
            ug = UserGraph()
            name = profile.get("name", "default") if profile else "default"

            lines = ["📊 Progress Dashboard\n"]
            if profile:
                levels = ", ".join(f"{k}: {v}" for k, v in profile.get("levels", {}).items())
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

    @staticmethod
    def cmd_ingest(topic: str, argument: str):
        if not argument:
            yield ChatEvent("status", "Usage: /ingest <path>")
            return
        from pathlib import Path

        target = Path(argument).expanduser()
        if not target.exists():
            yield ChatEvent("error", f"Path not found: {target}")
            return
        yield ChatEvent("status", "Ingesting...", {"busy": True})
        from pitagora.core.constants import SUPPORTED_FORMATS
        from pitagora.knowledge.base import KnowledgeBase
        from pitagora.knowledge.chunker import SmartChunker
        from pitagora.knowledge.ingester import DocumentIngester

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
                    kb.add_document(str(f), f.stem, topic, chunks=chunks)
                    count += 1
            except Exception:
                continue
        yield ChatEvent("status", f"✓ Ingested {count}/{len(files)} documents")

    @staticmethod
    def cmd_journeys(argument: str):
        try:
            from pitagora.journeys.store import list_journeys

            journeys = list_journeys()
            if not journeys:
                yield ChatEvent("status", "No journeys yet. Use /explore <topic>.")
                return
            icons = {"active": "🟢", "paused": "⏸", "completed": "✓", "abandoned": "✗"}
            lines = []
            for j in journeys:
                status_str = str(j.get("status")) if j.get("status") else "unknown"
                icon = icons.get(status_str, "•")
                lines.append(
                    f"  {icon} {j['id']} — {j['topic']} ({j.get('status', '?')}) "
                    f"— {j.get('interaction_count', 0)} interactions"
                )
            yield ChatEvent("markdown", "\n".join(lines))
        except Exception as e:
            yield ChatEvent("status", f"Journeys unavailable: {e}")

    @staticmethod
    def cmd_dashboard(argument: str):
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

    @staticmethod
    def cmd_quiz(state: ChatSessionState, argument: str):
        quiz_prompt = (
            f"Generate a practice problem on '{state.topic}' at intermediate level. "
            f"Format: state the problem clearly, then say HINTS: followed by hints. "
            f"Do NOT give the solution."
        )
        state.messages.append({"role": "user", "content": quiz_prompt})
        yield ChatEvent("status", "Generating quiz...", {"busy": True})
        response = state.completion(state.messages, model=state.model, config=state.config)
        state.messages.append({"role": "assistant", "content": response})
        yield ChatEvent("markdown", response)
        yield ChatEvent("state_changed", metadata={"context": state.context})

    @staticmethod
    def cmd_workflow(state: ChatSessionState, argument: str):
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
        from pitagora.core.constants import DEFAULT_API_KEY, DEFAULT_BASE_URL

        AVAILABLE_WORKFLOWS = (
            "teach",
            "derive_and_prove",
            "concept_mastery",
            "debate",
            "deep_research",
            "philosophical_reasoning",
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
                api_key=state.config.get("api_key", DEFAULT_API_KEY),
                model=state.model,
                base_url=state.config.get("base_url", DEFAULT_BASE_URL),
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
            inputs = {"topic": wf_arg or state.topic, "level": "intermediate"}
            yield ChatEvent("status", f"Running workflow '{wf_name}'...", {"busy": True})
            result = _asyncio.run(engine.execute(inputs, workflow_name_or_def=wf_name))
            final = result.get("final_output") or "(no output)"
            yield ChatEvent("markdown", final)
        except Exception as e:
            yield ChatEvent("error", f"Workflow failed: {e}")
