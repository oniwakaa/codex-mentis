"""Spaced repetition review command — daily practice to maintain mastery."""
import typer
from typing import Optional

app = typer.Typer(help="Spaced repetition review system")


@app.command("start")
def review_start(
    count: int = typer.Option(10, "--count", "-n", help="Number of cards to review"),
    subject: Optional[str] = typer.Option(None, "--subject", "-s", help="Filter by subject"),
):
    """Start a spaced repetition review session."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.markdown import Markdown
    from rich.text import Text
    from pitagora.memory.spaced_repetition import SpacedRepetition
    from pitagora.concepts.graph import ConceptGraph

    console = Console()
    sr = SpacedRepetition()
    cg = ConceptGraph()

    # Get due cards
    due = sr.get_due_reviews()

    if not due:
        console.print(Panel(
            "[green]No cards due for review! Your spaced repetition schedule is up to date.[/green]\n\n"
            "Cards appear for review based on the SM-2 algorithm:\n"
            "  - New cards: reviewed daily\n"
            "  - Learning cards: reviewed at increasing intervals\n"
            "  - Mastered cards: reviewed every few weeks\n\n"
            "[dim]Use `pitagora study <topic>` to add new concepts to your review deck.[/dim]",
            title="📚 Review Status",
            border_style="green",
        ))
        return

    console.print(Panel(
        f"[bold]Starting review session[/bold]\n"
        f"Cards due: [cyan]{len(due)}[/cyan]\n"
        f"Subject filter: [cyan]{subject or 'all'}[/cyan]",
        title="📚 Spaced Repetition Review",
        border_style="blue",
    ))

    correct = 0
    total = 0

    for i, card in enumerate(due, 1):
        concept = card.get("concept", "Unknown")
        interval = card.get("interval", 0)
        ease = card.get("ease_factor", 2.5)
        reps = card.get("repetitions", 0)

        # Get concept info from graph
        prereqs = cg.get_prerequisites(concept)
        prereq_str = ", ".join(prereqs[:3]) if prereqs else "none"

        console.print(f"\n[bold cyan]Card {i}/{len(due)}[/bold cyan]")
        console.print(f"[bold yellow]Concept:[/bold yellow] {concept}")
        if prereqs:
            console.print(f"[dim]Prerequisites: {prereq_str}[/dim]")
        console.print(f"[dim]Interval: {interval}d | Ease: {ease:.1f} | Reps: {reps}[/dim]")

        # Ask user to rate their recall
        console.print("\n[bold]Rate your recall:[/bold]")
        console.print("  [green]1[/green] = Perfect recall (no hesitation)")
        console.print("  [green]2[/green] = Good recall (minor hesitation)")
        console.print("  [yellow]3[/green] = Fair recall (some difficulty)")
        console.print("  [red]4[/red] = Poor recall (couldn't remember)")
        console.print("  [red]5[/red] = No recall at all")
        console.print("  [dim]s[/dim] = Skip this card")

        rating = Prompt.ask(
            "Your rating",
            choices=["1", "2", "3", "4", "5", "s"],
            default="s",
        )

        if rating == "s":
            console.print("[dim]Skipped[/dim]")
            continue

        total += 1
        rating_int = int(rating)

        # Update SM-2 algorithm
        sr.update_score(concept, quality=rating_int)

        if rating_int <= 2:
            correct += 1
            next_date = sr.get_review_metrics(concept).get("next_review", "?")
            console.print(f"[green]✓ Recorded — next review: {next_date}[/green]")
        else:
            console.print(f"[yellow]↺ Will review again sooner[/yellow]")

    # Show summary
    if total > 0:
        pct = (correct / total) * 100
        color = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
        console.print(Panel(
            f"[bold {color}]{correct}/{total} recalled ({pct:.0f}%)[/bold {color}]\n\n"
            f"{'Excellent work! Keep it up.' if pct >= 80 else 'Keep practicing — it gets easier with repetition.' if pct >= 50 else 'Consider revisiting these concepts with `pitagora study`.'}",
            title="📊 Review Summary",
            border_style=color,
        ))


@app.command("status")
def review_status():
    """Show spaced repetition status — how many cards are due."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from pitagora.memory.spaced_repetition import SpacedRepetition

    console = Console()
    sr = SpacedRepetition()

    stats = sr.get_performance_analytics()

    table = Table(title="Spaced Repetition Status", show_header=True)
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Status")

    new_count = stats.get("new_cards", 0)
    learning_count = stats.get("learning_cards", 0)
    review_count = stats.get("review_cards", 0)
    mature_count = stats.get("mature_cards", 0)

    table.add_row("New (never reviewed)", str(new_count), "🔵")
    table.add_row("Learning (intervals < 1d)", str(learning_count), "🟡")
    table.add_row("Review (intervals < 21d)", str(review_count), "🟠")
    table.add_row("Mature (intervals ≥ 21d)", str(mature_count), "🟢")

    console.print(table)

    if review_count > 0:
        console.print(f"\n[bold yellow]You have {review_count} cards due for review.[/bold yellow]")
        console.print("[dim]Run `pitagora review start` to begin.[/dim]")
    else:
        console.print("\n[green]No cards due — you're up to date![/green]")


@app.command("add")
def review_add(
    concept: str = typer.Argument(..., help="Concept to add to review deck"),
):
    """Add a concept to the spaced repetition deck."""
    from rich.console import Console
    from pitagora.memory.spaced_repetition import SpacedRepetition

    console = Console()
    sr = SpacedRepetition()
    sr.schedule_review(concept, quality=0)
    console.print(f"[green]✓ Added '{concept}' to review deck.[/green]")
    console.print("[dim]It will appear for review based on the SM-2 schedule.[/dim]")
