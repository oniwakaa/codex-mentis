from typing import List, Dict, Any, Optional, Tuple
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text

console = Console()

def print_markdown(content: str) -> None:
    """Renders standard markdown content using Rich."""
    md = Markdown(content)
    console.print(md)

def print_panel(content: str, title: str, style: str = "blue") -> None:
    """Prints a styled container panel."""
    panel = Panel(content, title=title, border_style=style, expand=False)
    console.print(panel)

def print_math(latex_str: str) -> None:
    """Renders math expression in terminal, falling back to unicode character cleaning if SymPy latex parser is absent."""
    console.print(f"[bold cyan]Math Formula:[/bold cyan]")
    try:
        from sympy.parsing.latex import parse_latex
        from sympy import pretty
        expr = parse_latex(latex_str)
        console.print(pretty(expr))
    except Exception:
        # Fallback substitution logic to make latex look clean in terminal
        clean = (
            latex_str
            .replace(r"\int", "∫")
            .replace(r"\sum", "∑")
            .replace(r"\alpha", "α")
            .replace(r"\beta", "β")
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
        )
        console.print(f"  [italic]{clean}[/italic]")

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
        # Theme setup
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
        # fallback text representation
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
