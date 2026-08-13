"""Teaching UI — Rich widgets for the teaching experience.

All functions print to a passed-in console (default: module-level Console).
Kept dependency-light: only rich, no new packages.
"""
from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

console = Console()

# Controls shown after each agent message in teaching mode.
CONTROLS_LINE = (
    "[cyan][n][/cyan] next  [cyan][e][/cyan] explain differently  "
    "[cyan][d][/cyan] go deeper  [cyan][s][/cyan] skip  [cyan][?][/cyan] confused  "
    "[cyan][v][/cyan] visualize  [cyan][q][/cyan] quiz  [cyan][p][/cyan] pause  "
    "[cyan]/help[/cyan]"
)


def build_controls() -> Text:
    return Text.from_markup(CONTROLS_LINE)

def show_controls(con: Console | None = None) -> None:
    (con or console).print(build_controls())


def _score_color(score: float) -> str:
    if score >= 0.8:
        return "green"
    if score >= 0.5:
        return "yellow"
    return "red"


def build_comprehension_gauge(score: float) -> Text:
    color = _score_color(score)
    bar_width = 20
    filled = round(score * bar_width)
    return Text.assemble(
        ("█" * filled + "░" * (bar_width - filled), color),
        f" {score * 100:5.1f}% comprehension",
    )

def show_comprehension_gauge(score: float, con: Console | None = None) -> None:
    """Render comprehension as a colored progress bar."""
    (con or console).print(build_comprehension_gauge(score))


def build_subconcept_progress(
    sub_concepts: list[dict[str, Any]],
    current_index: int,
    compact: bool = False,
):
    lines: list[str] = []
    parts = []
    for i, sc in enumerate(sub_concepts):
        marker = "▸ " if i == current_index else ("" if compact else "  ")
        name = sc.get("name", "?")
        mastery = float(sc.get("mastery", 0.0))
        visited = bool(sc.get("visited", False))
        if not visited:
            if compact:
                parts.append((f"{marker}{name}", "dim"))
            else:
                lines.append(f"{marker}[dim]{name}[/dim]")
        else:
            color = _score_color(mastery)
            if compact:
                parts.append((f"{marker}{name} ({mastery*100:.0f}%)", color))
            else:
                lines.append(f"{marker}[{color}]{name}[/{color}] ({mastery*100:.0f}%)")
    
    if compact:
        t = Text()
        for i, (text, style) in enumerate(parts):
            if i > 0:
                t.append("; ", style="dim")
            t.append(text, style=style)
        return t
    else:
        return Panel("\n".join(lines), title="Sub-concepts", border_style="blue")

def show_subconcept_progress(
    sub_concepts: list[dict[str, Any]],
    current_index: int,
    con: Console | None = None,
) -> None:
    """Render sub-concept list with mastery colors and a current marker."""
    (con or console).print(build_subconcept_progress(sub_concepts, current_index))


def show_topic_overview(
    topic: str,
    sub_concepts: list[str],
    level: str = "intermediate",
    prerequisites: list[str] | None = None,
    con: Console | None = None,
) -> None:
    con = con or console
    body = [f"[bold]Topic:[/bold] {topic}", f"[bold]Level:[/bold] {level}"]
    if prerequisites:
        body.append(f"[bold]Prerequisites:[/bold] {', '.join(prerequisites)}")
    body.append("[bold]We'll cover:[/bold]")
    for i, sc in enumerate(sub_concepts, 1):
        body.append(f"  {i}. {sc}")
    con.print(Panel("\n".join(body), title="Topic Overview", border_style="cyan"))


def show_session_summary(
    topic: str,
    comprehension: float,
    interaction_count: int,
    best_style: str,
    mastered: list[str],
    con: Console | None = None,
) -> None:
    con = con or console
    rows = [
        ("Topic", topic),
        ("Final comprehension", f"{comprehension*100:.1f}%"),
        ("Interactions", str(interaction_count)),
        ("Best style", best_style),
        ("Mastered sub-concepts", ", ".join(mastered) if mastered else "—"),
    ]
    t = Table(title="Session Summary", show_header=False, border_style="green")
    t.add_column("k", style="bold")
    t.add_column("v")
    for k, v in rows:
        t.add_row(k, v)
    con.print(t)


def show_journey_map(
    topic: str,
    sub_concepts: list[dict[str, Any]],
    con: Console | None = None,
) -> None:
    """Render a concept tree with mastery colors."""
    con = con or console
    root = Tree(f"[bold green]{topic}[/bold green]")
    for sc in sub_concepts:
        name = sc.get("name", "?")
        mastery = float(sc.get("mastery", 0.0))
        visited = bool(sc.get("visited", False))
        if not visited:
            root.add(f"[dim]{name}[/dim]")
        else:
            color = _score_color(mastery)
            root.add(f"[{color}]{name}[/{color}] ({mastery*100:.0f}%)")
    con.print(root)
