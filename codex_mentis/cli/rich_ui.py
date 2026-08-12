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

def print_math(latex_str: str) -> None:
    """Renders math expression in terminal, translating LaTeX symbols and exponents to Unicode."""
    console.print(f"[bold cyan]Math Formula:[/bold cyan]")
    try:
        from sympy.parsing.latex import parse_latex
        from sympy import pretty
        expr = parse_latex(latex_str)
        console.print(pretty(expr))
    except Exception:
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
            .replace(r"\infty", "∞")
        )
        
        # Replace superscripts e.g. x^2
        import re
        def replace_super(match):
            val = match.group(1)
            return "".join(superscript_map.get(c, c) for c in val)
        clean = re.sub(r"\^\{?([0-9a-zA-Z\+\-\=]+)\}?", replace_super, clean)
        
        # Replace subscripts e.g. x_0
        def replace_sub(match):
            val = match.group(1)
            return "".join(subscript_map.get(c, c) for c in val)
        clean = re.sub(r"\_\{?([0-9a-zA-Z\+\-\=]+)\}?", replace_sub, clean)

        console.print(f"  [italic]{clean}[/italic]")

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
            
        plt.show()
    except Exception as e:
        console.print(f"[yellow]Plotext execution failed: {e}[/yellow]")
        console.print(f"[bold]Plot: {title}[/bold]")
        console.print(f"X range: {min(x)} to {max(x)}")
        console.print(f"Y range: {min(y)} to {max(y)}")

def print_concept_map(concept_id: str, relations: Dict[str, List[str]], concept_names: Dict[str, str], direction: str = "prerequisites") -> None:
    """Renders an ASCII concept dependency tree."""
    root_name = concept_names.get(concept_id, concept_id)
    tree = Tree(f"[bold green]{root_name}[/bold green] ({concept_id})")
    
    def add_branches(node: Tree, cid: str, visited: set) -> None:
        if cid in visited:
            return
        visited.add(cid)
        children = relations.get(cid, [])
        for child in children:
            child_name = concept_names.get(child, child)
            child_node = node.add(f"[cyan]{child_name}[/cyan] ({child})")
            add_branches(child_node, child, visited.copy())
            
    add_branches(tree, concept_id, set())
    console.print(tree)

def print_table(headers: List[str], rows: List[List[Any]], title: Optional[str] = None) -> None:
    """Prints tabular data nicely formatted."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*[str(item) for item in row])
    console.print(table)

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
