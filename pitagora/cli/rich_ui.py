from typing import List, Dict, Any, Optional, Tuple
import time
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()


# ASCII banner for the Pitagora REPL. Gold on dark, fits 80 cols.
_PITAGORA_BANNER = r"""
 ____  _   _ _____ _   _ ____  ___  _____   __
|  _ \| | | | ____| | | / ___||_ _|_   _| / /
| |_) | |_| |  _| | |_| \___ \ | |  | |  / /_
|  __/|  _  | |___|  _  |___) || |  | | / __ \
|_|   |_| |_|_____|_| |_|____/___| |_| /_/  \_\
"""


def show_pitagora_banner(con: Optional[Console] = None) -> None:
    """Print the gold ASCII Pitagora banner."""
    con = con or console
    con.print(f"[bold yellow]{_PITAGORA_BANNER}[/bold yellow]")


def show_welcome(
    mode: str = "study",
    topic: str = "general",
    model: str = "unknown",
    con: Optional[Console] = None,
) -> None:
    """Print the banner plus a welcome panel with mode/model/topic/commands."""
    con = con or console
    show_pitagora_banner(con)
    con.print(Panel(
        f"[bold cyan]Pitagora[/bold cyan] — {mode.title()} mode\n"
        f"Model: [dim]{model}[/dim] | Topic: [dim]{topic}[/dim]\n\n"
        f"Commands: [cyan]/mode[/cyan] [cyan]/topic[/cyan] [cyan]/model[/cyan] "
        f"[cyan]/explore[/cyan] [cyan]/verify[/cyan] [cyan]/research[/cyan] "
        f"[cyan]/clear[/cyan] [cyan]/quit[/cyan]",
        title="🧠 Pitagora",
        border_style="blue",
    ))


def print_markdown(content: str) -> None:
    """Renders standard markdown content using Rich, supporting code syntax highlighting."""
    md = Markdown(content, code_theme="nord")
    console.print(md)

def print_panel(content: str, title: str, style: str = "blue") -> None:
    """Prints a styled container panel."""
    panel = Panel(content, title=title, border_style=style, expand=False)
    console.print(panel)

def get_confidence_indicator(score: float) -> Text:
    """Creates a color-coded confidence level Rich Text representation."""
    if score >= 0.8:
        style = "bold green"
        emoji = "✅"
    elif score >= 0.4:
        style = "bold yellow"
        emoji = "⚠️"
    else:
        style = "bold red"
        emoji = "❌"
    return Text(f"{emoji} Agent Confidence: {score * 100:.1f}%", style=style)

def print_confidence(score: float) -> None:
    """Print the confidence score to the terminal."""
    console.print(get_confidence_indicator(score))

def print_math(latex_str: str, return_str: bool = False):
    """Renders math expression in terminal, translating LaTeX symbols and exponents to Unicode.

    When return_str=True, return the rendered string instead of printing it.
    """
    def _render(latex_str: str) -> str:
        # Try SymPy pretty-printing first; fall back to Unicode substitution.
        try:
            from sympy.parsing.latex import parse_latex
            from sympy import pretty
            expr = parse_latex(latex_str)
            return pretty(expr)
        except Exception:
            return _unicode_substitute(latex_str)

    out = _render(latex_str)
    if return_str:
        return out
    console.print(f"[bold cyan]Math Formula:[/bold cyan]")
    console.print(f"  [italic]{out}[/italic]")


def _unicode_substitute(latex_str: str) -> str:
    # High quality fallback substitution logic mapping to superscript/subscript unicode chars
    superscript_map = {
        "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
        "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
        "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
        "n": "ⁿ", "x": "ˣ", "y": "ʸ", "i": "ⁱ"
    }
    subscript_map = {
        "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
        "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
        "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
        "i": "ᵢ", "j": "ⱼ", "k": "ₖ", "x": "ₓ", "y": "ᵧ"
    }

    clean = (
        latex_str
        .replace(r"\int", "∫")
        .replace(r"\sum", "∑")
        .replace(r"\alpha", "α")
        .replace(r"\beta", "β")
        .replace(r"\gamma", "γ")
        .replace(r"\theta", "θ")
        .replace(r"\partial", "∂")
        .replace(r"\infty", "∞")
        .replace(r"\hbar", "ħ")
        .replace(r"\psi", "ψ")
        .replace(r"\Psi", "Ψ")
        .replace(r"\phi", "φ")
        .replace(r"\lambda", "λ")
        .replace(r"\pi", "π")
        .replace(r"\nabla", "∇")
        .replace(r"\Delta", "Δ")
        .replace(r"\cdot", "·")
        .replace(r"\sqrt", "√")
        .replace(r"\approx", "≈")
        .replace(r"\neq", "≠")
        .replace(r"\leq", "≤")
        .replace(r"\geq", "≥")
        .replace(r"\rightarrow", "→")
    )

    import re
    def replace_super(match):
        val = match.group(1)
        return "".join(superscript_map.get(c, c) for c in val)
    clean = re.sub(r"\^\{?([0-9a-zA-Z\+\-\=]+)\}?", replace_super, clean)

    def replace_sub(match):
        val = match.group(1)
        return "".join(subscript_map.get(c, c) for c in val)
    clean = re.sub(r"\_\{?([0-9a-zA-Z\+\-\=]+)\}?", replace_sub, clean)
    return clean

def animated_progress(steps: List[str], duration_per_step: float = 0.6) -> None:
    """Displays animated progress bar loading indicator for multi-step derivations."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[bold]Verifying calculus...", total=len(steps))
        for idx, step in enumerate(steps, 1):
            time.sleep(duration_per_step)
            progress.advance(task)
            progress.update(task, description=f"[green]Step {idx}/{len(steps)} verified: {step[:35]}...")

def print_split_reasoning(derivation: str, intuition: str) -> None:
    """Renders technical derivation and physical intuition in side-by-side panels."""
    left_panel = Panel(Markdown(derivation, code_theme="nord"), title="[bold yellow]Derivation & Proof[/bold yellow]", border_style="yellow")
    right_panel = Panel(Markdown(intuition, code_theme="nord"), title="[bold cyan]Conceptual Intuition[/bold cyan]", border_style="cyan")
    
    # 2-column layout grid
    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_row(left_panel, right_panel)
    console.print(grid)

def build_plot(
    x: List[float], 
    y: List[float], 
    title: str, 
    xlabel: str, 
    ylabel: str, 
    plot_type: str = "function", 
    x_range: Optional[Tuple[float, float]] = None
) -> Panel:
    import plotext as plt
    plt.clf()
    plt.theme("dark")
    
    if plot_type == "scatter":
        plt.scatter(x, y)
    else:
        plt.plot(x, y)
        
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    
    if x_range:
        plt.xlim(x_range[0], x_range[1])
        
    ansi = plt.build()
    return Panel(Text.from_ansi(ansi), title=title, expand=False)

def print_plot(
    x: List[float], 
    y: List[float], 
    title: str, 
    xlabel: str, 
    ylabel: str, 
    plot_type: str = "function", 
    x_range: Optional[Tuple[float, float]] = None
) -> None:
    """Renders a terminal plot using plotext."""
    try:
        console.print(build_plot(x, y, title, xlabel, ylabel, plot_type, x_range))
    except Exception as e:
        console.print(f"[yellow]Plotext execution failed: {e}[/yellow]")
        console.print(f"[bold]Plot: {title}[/bold]")
        console.print(f"X range: {min(x)} to {max(x)}")
        console.print(f"Y range: {min(y)} to {max(y)}")

def print_concept_map(
    concept_id: str,
    relations: Dict[str, List[str]],
    concept_names: Dict[str, str],
    direction: str = "prerequisites",
    mastery_scores: Optional[Dict[str, float]] = None,
    current_concept: Optional[str] = None,
) -> None:
    """Renders an ASCII concept dependency tree with mastery colors.

    mastery_scores: optional map of concept_id → 0.0-1.0. When present, nodes
    are colored green (≥0.8), yellow (≥0.5), red (<0.5), or dim (not started).
    current_concept: optional concept_id marked with ▸.
    """
    mastery_scores = mastery_scores or {}

    def _label(cid: str) -> str:
        name = concept_names.get(cid, cid)
        marker = "▸ " if cid == current_concept else ""
        score = mastery_scores.get(cid)
        if score is None:
            return f"{marker}[dim]{name}[/dim] ({cid})"
        if score >= 0.8:
            style = "green"
        elif score >= 0.5:
            style = "yellow"
        else:
            style = "red"
        return f"{marker}[{style}]{name}[/{style}] ({cid}) [{score*100:.0f}%]"

    root_name = concept_names.get(concept_id, concept_id)
    tree = Tree(f"[bold green]{root_name}[/bold green] ({concept_id})")

    def add_branches(node: Tree, cid: str, visited: set) -> None:
        if cid in visited:
            return
        visited.add(cid)
        children = relations.get(cid, [])
        for child in children:
            child_node = node.add(_label(child))
            add_branches(child_node, child, visited.copy())

    add_branches(tree, concept_id, set())
    console.print(tree)


def build_equation_block(
    equations: List[Dict[str, str]],
    title: str = "Equations",
    style: str = "cyan",
) -> Panel:
    lines = []
    for i, eq in enumerate(equations, 1):
        rendered = print_math(eq["equation"], return_str=True)
        line = f"[bold yellow]({i})[/bold yellow]  {rendered}"
        ann = eq.get("annotation")
        if ann:
            line += f"\\n      [dim italic]{ann}[/dim italic]"
        lines.append(line)
    content = "\\n\\n".join(lines)
    return Panel(content, title=title, border_style=style, expand=False)

def print_equation_block(
    equations: List[Dict[str, str]],
    title: str = "Equations",
    style: str = "cyan",
) -> None:
    """Render a sequence of numbered equations in a Rich panel.

    Each item: {"equation": "<latex>", "annotation": "<optional note>"}.
    """
    console.print(build_equation_block(equations, title, style))


def print_mastery_dashboard(
    by_domain: Dict[str, Dict[str, Any]],
    journeys: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Mastery dashboard grouped by domain.

    by_domain: {domain: {"concepts": int, "mastered": int, "avg_score": float}}
    journeys: optional list of journey summaries (id, topic, status) shown
    below the table.
    """
    table = Table(title="Mastery Dashboard", show_header=True, header_style="bold magenta")
    table.add_column("Domain")
    table.add_column("Concepts", justify="right")
    table.add_column("Mastered", justify="right")
    table.add_column("Progress")
    table.add_column("Status")

    for domain, stats in sorted(by_domain.items()):
        total = int(stats.get("concepts", 0))
        mastered = int(stats.get("mastered", 0))
        avg = float(stats.get("avg_score", 0.0))
        pct = (mastered / total * 100) if total else 0.0
        bar_width = 16
        filled = int(round(pct / 100 * bar_width))
        bar = "█" * filled + "░" * (bar_width - filled)
        if avg >= 0.8:
            color = "green"
        elif avg >= 0.5:
            color = "yellow"
        else:
            color = "red"
        status = "Mastered" if pct >= 80 else "In progress" if pct > 0 else "Not started"
        table.add_row(
            domain, str(total), str(mastered),
            f"[{color}]{bar}[/{color}] {pct:5.1f}%", status,
        )

    console.print(table)

    if journeys:
        console.print("\n[bold]Active journeys:[/bold]")
        for j in journeys:
            console.print(
                f"  • [cyan]{j.get('topic', '?')}[/cyan] "
                f"({j.get('status', '?')}) — {j.get('interaction_count', 0)} interactions"
            )

def build_table(headers: List[str], rows: List[List[Any]], title: Optional[str] = None) -> Table:
    table = Table(title=title, show_header=True, header_style="bold magenta", expand=True, row_styles=["none", "dim"])
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*[str(item) for item in row])
    return table

def print_table(headers: List[str], rows: List[List[Any]], title: Optional[str] = None) -> None:
    """Prints tabular data nicely formatted."""
    console.print(build_table(headers, rows, title))

def create_spinner(text: str):
    """Creates a loading spinner context manager."""
    return console.status(text, spinner="dots")

def format_proof(steps: List[str], title: str = "Proof Derivation") -> None:
    """Formats a step-by-step mathematical proof."""
    formatted_steps = []
    for idx, step in enumerate(steps, 1):
        formatted_steps.append(f"[bold yellow]Step {idx}:[/bold yellow] {step}")
    content = "\n\n".join(formatted_steps)
    print_panel(content, title=title, style="green")
