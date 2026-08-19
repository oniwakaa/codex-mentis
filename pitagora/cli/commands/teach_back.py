"""CLI command for Feynman Teach-Back Sandbox."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from pitagora.chat import chat_completion, load_provider_config
from pitagora.teaching.feynman import FeynmanSession

app = typer.Typer(help="Feynman reverse-teaching mode (teach-back sandbox)")


@app.callback(invoke_without_command=True)
def teach_back_main(
    ctx: typer.Context,
    concept: str = typer.Argument(..., help="The concept you want to teach (e.g., 'Special Relativity', 'Bayes Theorem', 'Ship of Theseus')"),
    domain: str = typer.Option("STEM/Philosophy", "--domain", "-d", help="Domain context"),
    turns: int = typer.Option(3, "--turns", "-t", help="Maximum student inquiry turns"),
):
    """Teach a concept to Pitagora. Pitagora acts as a curious student and evaluates your explanation."""
    if ctx.invoked_subcommand is not None:
        return

    console = Console()
    config = load_provider_config()
    session = FeynmanSession(concept=concept, domain=domain, chat_completion_fn=chat_completion)

    console.print(
        Panel(
            f"[bold gold1]△ FEYNMAN TEACH-BACK SANDBOX[/bold gold1]\n\n"
            f"[bold]Target Concept:[/bold] [cyan]{concept}[/cyan] ({domain})\n"
            f"[dim]Role: You are the Teacher. Pitagora is your curious student.\n"
            f"Rule: Explain from first principles. Avoid unexplained jargon. Use intuition & analogies.[/dim]",
            title="🧑‍🏫 Reverse Tutoring",
            border_style="gold1",
        )
    )

    console.print(f"\n[bold cyan]Student Pitagora:[/bold cyan] \"I am ready to learn! How would you explain [bold]{concept}[/bold] in your own words?\"\n")

    for turn in range(1, turns + 1):
        teacher_input = Prompt.ask(f"[bold green]Your Explanation (Turn {turn}/{turns})[/bold green]")
        if not teacher_input.strip() or teacher_input.strip().lower() in ["exit", "quit", "q"]:
            console.print("[dim]Ending session early...[/dim]")
            break

        with console.status("[cyan]Student is processing and formulating questions...[/cyan]"):
            eval_result = session.evaluate_explanation(teacher_input, config=config)

        rub = eval_result.rubric
        console.print(f"\n[dim]Turn {turn} Analysis ── Clarity: {rub.clarity*100:.0f}% | Precision: {rub.precision*100:.0f}% | Analogy: {rub.analogy*100:.0f}% | Depth: {rub.depth*100:.0f}%[/dim]")

        if eval_result.jargon_used:
            console.print(f"[yellow]⚠️ Jargon flagged (unpacked?):[/yellow] {', '.join(eval_result.jargon_used)}")
        if eval_result.misconceptions:
            console.print(f"[red]⚠️ Gap/Misconception logged:[/red] {', '.join(eval_result.misconceptions)}")

        if eval_result.is_mastered or turn == turns:
            break

        console.print(f"\n[bold cyan]Student Pitagora:[/bold cyan] \"{eval_result.student_question}\"\n")

    # Final Report
    report = session.generate_final_report()
    rub = report["rubric"]

    console.print("\n" + "=" * 55)
    console.print(f"[bold gold1]FEYNMAN TEACH-BACK ASSESSMENT REPORT: {concept}[/bold gold1]")
    console.print("=" * 55)

    table = Table(show_header=True)
    table.add_column("Dimension", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Rubric Feedback")

    def _badge(val: float) -> str:
        if val >= 0.8:
            return f"[green]{val*100:.0f}% (Mastered)[/green]"
        if val >= 0.5:
            return f"[yellow]{val*100:.0f}% (Developing)[/yellow]"
        return f"[red]{val*100:.0f}% (Needs Work)[/red]"

    table.add_row("Plain-Language Clarity", _badge(rub.clarity), "Simplicity & absence of ungrounded jargon")
    table.add_row("Axiomatic Precision", _badge(rub.precision), "Mathematical, physical, or logical correctness")
    table.add_row("Analogy & Intuition", _badge(rub.analogy), "Quality of concrete models and analogies")
    table.add_row("First-Principles Depth", _badge(rub.depth), "Depth of causal reasoning & edge-case handling")

    console.print(table)
    overall_color = "green" if report["overall_score"] >= 0.8 else "yellow" if report["overall_score"] >= 0.5 else "red"
    console.print(f"\n[bold {overall_color}]Overall Feynman Mastery: {report['overall_score']*100:.0f}%[/bold {overall_color}]")

    if report["all_misconceptions"]:
        console.print(f"[dim]Saved {len(report['all_misconceptions'])} misconceptions to memory & scheduled review cards.[/dim]")
    console.print("=" * 55 + "\n")
