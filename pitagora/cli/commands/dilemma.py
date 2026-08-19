"""CLI command for interactive Philosophical Dilemmas and Thought Experiments."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from pitagora.knowledge.dilemma import DilemmaEngine

app = typer.Typer(help="Interactive philosophical thought experiments & dilemma simulator")


@app.callback(invoke_without_command=True)
def dilemma_main(
    ctx: typer.Context,
    scenario_id: str = typer.Argument(None, help="Scenario ID (e.g., 'ship_of_theseus', 'chinese_room', 'maxwells_demon', 'trolley_fatman', 'newcomb_problem')"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List available thought experiments"),
):
    """Explore deep philosophical thought experiments and test epistemic consistency."""
    if ctx.invoked_subcommand is not None:
        return

    console = Console()
    engine = DilemmaEngine()

    if list_all:
        table = Table(title="🏛️ Pitagora Philosophical Thought Experiments", show_header=True)
        table.add_column("ID", style="bold cyan")
        table.add_column("Scenario Title", style="yellow")
        table.add_column("Domain", style="magenta")
        for sc in engine.list_scenarios():
            table.add_row(sc["id"], sc["title"], sc["domain"])
        console.print(table)
        console.print("\n[dim]Run `pitagora dilemma <id>` to enter an interactive thought experiment.[/dim]\n")
        return

    if not scenario_id:
        table = Table(title="🏛️ Pitagora Philosophical Thought Experiments", show_header=True)
        table.add_column("ID", style="bold cyan")
        table.add_column("Scenario Title", style="yellow")
        table.add_column("Domain", style="magenta")
        for sc in engine.list_scenarios():
            table.add_row(sc["id"], sc["title"], sc["domain"])
        console.print(table)
        console.print("\n[dim]Run `pitagora dilemma <id>` to enter an interactive thought experiment.[/dim]\n")
        scenario_id = Prompt.ask("Choose a scenario ID to explore", default="ship_of_theseus")

    scenario = engine.get_scenario(scenario_id)
    if not scenario:
        console.print(f"[red]Error: Unknown scenario '{scenario_id}'. Use --list to view available dilemmas.[/red]")
        return

    console.print(
        Panel(
            f"[bold gold1]{scenario.title}[/bold gold1]\n"
            f"[magenta]Domain:[/magenta] {scenario.domain}\n\n"
            f"{scenario.premise}",
            title="🏛️ Philosophical Thought Experiment",
            border_style="gold1",
        )
    )

    console.print("\n[bold cyan]What is your position?[/bold cyan]")
    for c in scenario.choices:
        console.print(f"  [bold green]{c.key})[/bold green] {c.label}")

    choice = Prompt.ask("\nYour choice", choices=[c.key for c in scenario.choices] + ["q"], default="A")
    if choice.lower() == "q":
        return

    result = engine.record_choice(scenario.id, choice)
    console.print("\n" + "=" * 55)
    console.print(f"[bold cyan]Philosophical Stance:[/bold cyan] {result['stance']}")
    console.print(f"[bold yellow]Implications:[/bold yellow] {result['implications']}")
    console.print(f"\n[bold red]⚡ Socratic Counter-Probe:[/bold red] {result['counter_probe']}")
    console.print(f"\n[bold green]Deep Synthesis:[/bold green] {result['deep_reflection']}")
    console.print(f"[dim]Key Thinkers: {', '.join(result['traditions'])}[/dim]")
    console.print("=" * 55 + "\n")
