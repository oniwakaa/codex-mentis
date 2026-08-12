"""Codex Mentis CLI — the main entry point."""
import typer
from codex_mentis.cli.commands import (
    study,
    explore,
    reason,
    verify,
    visualize,
    concept,
    memory,
    kb,
    config,
    skills,
)

# New commands — lazy import to avoid loading heavy deps at import time
try:
    from codex_mentis.cli.commands import review
except ImportError:
    review = None

try:
    from codex_mentis.cli.commands import doctor
except ImportError:
    doctor = None

try:
    from codex_mentis.cli.commands import profile, session, onboard, ingest
except ImportError:
    profile = session = onboard = ingest = None

app = typer.Typer(
    name="codex-mentis",
    help="Codex Mentis: An AI-powered CLI for studying math and physics with multi-agent reasoning",
    no_args_is_help=False,
)

# Register command groups (Sub-apps)
app.add_typer(concept.app, name="concept")
app.add_typer(memory.app, name="memory")
app.add_typer(kb.app, name="kb")
app.add_typer(config.app, name="config")
app.add_typer(skills.app, name="skills")

# Register new command groups
if review:
    app.add_typer(review.app, name="review")
if doctor:
    app.add_typer(doctor.app, name="doctor")
if profile:
    app.add_typer(profile.app, name="profile")
if session:
    app.add_typer(session.app, name="session")

# Register single commands
if onboard:
    @app.command("onboard")
    def onboard_cmd(
        skip: bool = typer.Option(False, "--skip", help="Skip interactive assessment"),
        level: str = typer.Option(None, "--level", help="Set level directly: beginner/intermediate/advanced"),
    ):
        """First-run onboarding with level assessment."""
        onboard.run_onboarding(skip=skip, level_override=level)

if ingest:
    app.add_typer(ingest.app, name="ingest")

# Register single commands
app.command("study")(study.study)
app.command("explore")(explore.explore)
app.command("derive")(reason.derive)
app.command("verify")(verify.verify)
app.command("plot")(visualize.plot_expression)


@app.command("research")
def research_cmd(
    topic: str = typer.Argument(..., help="Topic to research"),
    depth: str = typer.Option("medium", help="Research depth: shallow, medium, deep"),
    save: bool = typer.Option(True, help="Save findings to knowledge base"),
):
    """Research a topic using web-acquired knowledge with full citations."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from codex_mentis.knowledge.acquisition import KnowledgeAcquisition
    from codex_mentis.knowledge.base import KnowledgeBase

    console = Console()
    console.print(f"[bold cyan]Researching:[/bold cyan] {topic} (depth={depth})")

    kb = KnowledgeBase() if save else None
    acquirer = KnowledgeAcquisition(knowledge_base=kb)
    result = acquirer.research_topic(topic, depth=depth)

    # Display results
    if result.get("citations"):
        md = f"## Research Results: {topic}\n\n"
        md += f"**Sources crawled:** {result['total_sources_crawled']}\n\n"

        if result.get("findings"):
            md += "### Key Findings\n\n"
            for i, finding in enumerate(result["findings"][:20], 1):
                md += f"{i}. {finding}\n\n"

        if result.get("concepts_found"):
            md += "### Concepts Discovered\n\n"
            for concept in result["concepts_found"]:
                md += f"- {concept}\n\n"

        md += "### Sources\n\n"
        for src in result["sources"]:
            md += f"- [{src['title']}]({src['url']})\n"

        console.print(Markdown(md))
    else:
        console.print(f"[yellow]No results found for '{topic}'. Try a different query.[/yellow]")


@app.command("explain")
def explain_cmd(
    topic: str = typer.Argument(..., help="Topic to explain"),
    level: str = typer.Option("intermediate", help="Level: child, beginner, intermediate, advanced, expert"),
    side_by_side: bool = typer.Option(False, "--side-by-side", "-s", help="Show technical + intuition side by side"),
):
    """Explain a complex topic at your level using the Feynman technique."""
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from codex_mentis.agents.explainer import ExplainerAgent

    console = Console()
    console.print(f"[bold cyan]Explaining:[/bold cyan] {topic} (level={level})")

    # Use a dummy provider for now — in production this would use config
    try:
        import asyncio
        from codex_mentis.agents.providers import create_provider
        from codex_mentis.agents.providers.base import ProviderConfig
        from codex_mentis.core.config import load_config
        cfg = load_config()
        provider = create_provider(ProviderConfig(model="gpt-4o"))
        agent = ExplainerAgent(provider=provider)

        if side_by_side:
            result = asyncio.run(agent.side_by_side_explanation(topic))
        else:
            result = asyncio.run(agent.explain_level(topic, level=level))

        console.print(Markdown(result.content))
    except Exception as e:
        # Fallback to mock explanation
        console.print(Panel(
            f"**Topic:** {topic}\n**Level:** {level}\n\n"
            f"The Explainer agent would break this down using the Feynman technique.\n"
            f"Configure a provider in ~/.codex-mentis/config.yaml to enable.\n\n"
            f"Error: {e}",
            title=f"Explanation: {topic}",
            border_style="cyan",
        ))


@app.command("debate")
def debate_cmd(
    topic: str = typer.Argument(..., help="Topic to debate"),
    rounds: int = typer.Option(3, help="Number of debate rounds"),
):
    """Run a structured debate between Prover and Reviewer agents."""
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    console.print(f"[bold yellow]Debate:[/bold yellow] {topic} ({rounds} rounds)")
    console.print("[dim]In production, this runs Prover vs Reviewer with a Synthesizer verdict.[/dim]")


@app.command("chat")
def chat_cmd():
    """Launch the interactive REPL shell."""
    from codex_mentis.cli.repl import launch_repl
    launch_repl()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    tui: bool = typer.Option(True, "--tui", "-t", help="Launch the Textual TUI interface (default)"),
    repl: bool = typer.Option(False, "--repl", "-r", help="Launch the line-based REPL shell instead of the TUI")
):
    """Entrypoint callback which boots the TUI (default) or REPL if requested."""
    if ctx.invoked_subcommand is None:
        if repl:
            from codex_mentis.cli.repl import launch_repl
            launch_repl()
        else:
            try:
                from codex_mentis.cli.tui import launch_tui
                launch_tui()
            except Exception as e:
                from codex_mentis.cli.repl import launch_repl
                launch_repl()


if __name__ == "__main__":
    app()
