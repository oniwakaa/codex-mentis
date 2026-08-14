"""Pitagora CLI — the main entry point."""

import logging
import os
import sys

import typer

from pitagora.cli.commands import (
    concept,
    config,
    data,
    explore,
    kb,
    memory,
    reason,
    skills,
    strategy,
    study,
    verify,
    visualize,
)

log = logging.getLogger(__name__)


def _is_interactive() -> bool:
    """Return whether both standard input and output are terminals."""
    return bool(sys.stdin and sys.stdout and sys.stdin.isatty() and sys.stdout.isatty())


def _load_simple_launcher():
    from pitagora.chat import launch_chat

    return launch_chat


def _load_tui_launcher():
    from pitagora.cli.tui import launch_tui

    return launch_tui


def _select_chat_launcher(simple: bool):
    if simple or not _is_interactive():
        return _load_simple_launcher()

    try:
        return _load_tui_launcher()
    except ModuleNotFoundError as exc:
        if exc.name != "textual" and not (exc.name and exc.name.startswith("textual.")):
            raise
        typer.echo(
            "Textual is not installed; install it with "
            "`pip install pitagora[tui]`. Falling back to simple chat."
        )
        return _load_simple_launcher()


# Lazy imports for optional command groups
try:
    from pitagora.cli.commands import review
except ImportError as e:
    log.warning("Failed to import %s: %s", "review", e)
    review = None

try:
    from pitagora.cli.commands import doctor
except ImportError as e:
    log.warning("Failed to import %s: %s", "doctor", e)
    doctor = None

try:
    from pitagora.cli.commands import ingest, onboard, profile, session, setup
except ImportError as e:
    log.warning("Failed to import %s: %s", "profile, session, onboard, ingest, setup", e)
    profile = session = onboard = ingest = setup = None

app = typer.Typer(
    name="pitagora",
    help="Pitagora: AI-powered math & physics learning CLI with multi-agent reasoning",
    no_args_is_help=False,
)

# Register command groups
app.add_typer(concept.app, name="concept")
app.add_typer(memory.app, name="memory")
app.add_typer(kb.app, name="kb")
app.add_typer(config.app, name="config")
app.add_typer(skills.app, name="skills")
app.add_typer(strategy.app, name="strategy")
app.add_typer(data.app, name="data")

if review:
    app.add_typer(review.app, name="review")
if doctor:
    app.add_typer(doctor.app, name="doctor")
if profile:
    app.add_typer(profile.app, name="profile")
if session:
    app.add_typer(session.app, name="session")
if setup:
    app.add_typer(setup.app, name="setup")
if ingest:
    app.add_typer(ingest.app, name="ingest")

# Onboarding command
if onboard:

    @app.command("onboard")
    def onboard_cmd(
        skip: bool = typer.Option(False, "--skip", help="Skip interactive assessment"),
        level: str = typer.Option(
            None, "--level", help="Set level: beginner/intermediate/advanced"
        ),
    ):
        """First-run onboarding with level assessment."""
        onboard.run_onboarding(skip=skip, level_override=level)


# Core commands
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
    from rich.markdown import Markdown

    from pitagora.knowledge.acquisition import KnowledgeAcquisition
    from pitagora.knowledge.base import KnowledgeBase

    console = Console()
    console.print(f"[bold cyan]Researching:[/bold cyan] {topic} (depth={depth})")

    knowledge_base = KnowledgeBase() if save else None
    acquirer = KnowledgeAcquisition(knowledge_base=knowledge_base)
    result = acquirer.research_topic(topic, depth=depth)

    if result.get("citations"):
        md = f"## Research Results: {topic}\n\n"
        md += f"**Sources crawled:** {result['total_sources_crawled']}\n\n"
        if result.get("findings"):
            md += "### Key Findings\n\n"
            for i, finding in enumerate(result["findings"][:20], 1):
                md += f"{i}. {finding}\n\n"
        if result.get("concepts_found"):
            md += "### Concepts Discovered\n\n"
            for c in result["concepts_found"]:
                md += f"- {c}\n\n"
        md += "### Sources\n\n"
        for src in result["sources"]:
            md += f"- [{src['title']}]({src['url']})\n"
        console.print(Markdown(md))
    else:
        console.print(f"[yellow]No results found for '{topic}'.[/yellow]")


@app.command("explain")
def explain_cmd(
    topic: str = typer.Argument(..., help="Topic to explain"),
    level: str = typer.Option(
        "intermediate", help="Level: child, beginner, intermediate, advanced, expert"
    ),
    side_by_side: bool = typer.Option(
        False, "--side-by-side", "-s", help="Technical + intuition side by side"
    ),
):
    """Explain a complex topic at your level using the Feynman technique."""
    from rich.console import Console
    from rich.markdown import Markdown

    from pitagora.chat import chat_completion, load_provider_config

    console = Console()
    config = load_provider_config()

    prompt = (
        f"Explain '{topic}' at a {level} level using the Feynman technique. "
        f"{'Show technical derivation and plain English intuition side by side.' if side_by_side else ''}"
        f"Use LaTeX notation for equations. Be clear and use analogies."
    )

    messages = [
        {"role": "system", "content": "You are Pitagora, an expert math/physics explainer."},
        {"role": "user", "content": prompt},
    ]

    with console.status("[bold cyan]Generating explanation...[/bold cyan]"):
        response = chat_completion(messages, config=config)

    console.print(Markdown(response))


@app.command("debate")
def debate_cmd(
    topic: str = typer.Argument(..., help="Topic to debate"),
    rounds: int = typer.Option(3, help="Number of debate rounds"),
):
    """Run a structured debate between Prover and Reviewer agents."""
    from rich.console import Console
    from rich.markdown import Markdown

    from pitagora.chat import chat_completion, load_provider_config

    console = Console()
    config = load_provider_config()

    # Prover argues FOR
    prover_prompt = (
        f"You are a mathematical prover. Argue IN FAVOR of the claim: '{topic}'. "
        f"Use formal reasoning, equations, and evidence. Be rigorous and persuasive."
    )
    reviewer_prompt = (
        f"You are an adversarial reviewer. Argue AGAINST the claim: '{topic}'. "
        f"Find counterexamples, edge cases, and logical flaws. Be rigorous."
    )

    console.print(f"[bold yellow]Debate:[/bold yellow] {topic}\n")

    prover_msgs = [{"role": "system", "content": prover_prompt}]
    reviewer_msgs = [{"role": "system", "content": reviewer_prompt}]

    prover_resp = ""
    reviewer_resp = ""

    for round_num in range(1, rounds + 1):
        console.print(f"[bold]Round {round_num}[/bold]")

        # Prover
        prover_msgs.append(
            {"role": "user", "content": f"Present your argument (round {round_num})."}
        )
        with console.status("[cyan]Prover thinking...[/cyan]"):
            prover_resp = chat_completion(prover_msgs, config=config)
        prover_msgs.append({"role": "assistant", "content": prover_resp})
        console.print(f"[green]Prover:[/green] {prover_resp[:500]}...\n")

        # Reviewer responds
        reviewer_msgs.append(
            {"role": "user", "content": f"Counter the prover's argument: {prover_resp}"}
        )
        with console.status("[cyan]Reviewer thinking...[/cyan]"):
            reviewer_resp = chat_completion(reviewer_msgs, config=config)
        reviewer_msgs.append({"role": "assistant", "content": reviewer_resp})
        console.print(f"[red]Reviewer:[/red] {reviewer_resp[:500]}...\n")

    # Synthesis
    synthesis_prompt = (
        f"Synthesize this debate about '{topic}'.\n\n"
        f"Prover's final argument: {prover_resp}\n\n"
        f"Reviewer's final argument: {reviewer_resp}\n\n"
        f"Give a balanced verdict with confidence score."
    )
    with console.status("[cyan]Synthesizing...[/cyan]"):
        verdict = chat_completion([{"role": "user", "content": synthesis_prompt}], config=config)

    console.print("\n[bold]Verdict:[/bold]\n")
    console.print(Markdown(verdict))


@app.command("chat")
def chat_cmd(
    ctx: typer.Context,
    mode: str = typer.Option("study", help="Mode: study/explore/reason/verify"),
    topic: str = typer.Option("general", help="Initial topic"),
    model: str = typer.Option(None, help="Override model"),
    simple: bool = typer.Option(False, "--simple", help="Use the simple chat interface"),
):
    """Launch the interactive chat REPL — the main experience."""
    if model:
        os.environ["PITAGORA_MODEL"] = model

    launcher = _select_chat_launcher(simple or bool(ctx.obj and ctx.obj.get("simple")))
    launcher(mode=mode, topic=topic)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    model: str = typer.Option(None, "--model", "-m", help="Override model"),
    simple: bool = typer.Option(False, "--simple", help="Use the simple chat interface"),
):
    """Pitagora — AI-powered math & physics learning.

    Running without a command launches the interactive chat.
    """
    ctx.ensure_object(dict)
    ctx.obj["simple"] = simple

    if ctx.invoked_subcommand is not None:
        return

    # WS4b: first-run wizard. Launch the interactive setup wizard when no
    # config exists AND stdin is a TTY (interactive use). In non-interactive
    # contexts (CI, pipes), fall back to a one-line hint + defaults so the
    # command never blocks on a prompt.
    from pitagora.core.constants import CONFIG_PATH

    if not CONFIG_PATH.exists():
        if sys.stdin and sys.stdin.isatty():
            try:
                from pitagora.cli.commands.setup import run_setup

                typer.echo("First run detected — launching setup wizard.\n")
                run_setup()
            except Exception as e:
                typer.echo(f"Setup wizard failed ({e}); continuing with defaults.")
        else:
            typer.echo(
                "First run detected — no config at ~/.pitagora/config.yaml. "
                "Run `pitagora setup` to configure providers and MCP servers. "
                "Continuing with defaults for now."
            )

    if model:
        os.environ["PITAGORA_MODEL"] = model

    launcher = _select_chat_launcher(simple)
    launcher()


if __name__ == "__main__":
    app()
