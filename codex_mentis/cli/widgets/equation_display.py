from typing import Optional
from textual.widget import Widget
from textual.widgets import Static
from rich.text import Text
from rich.panel import Panel

def latex_to_unicode(latex_str: str) -> str:
    """Helper to convert LaTeX symbols to readable unicode characters."""
    if not latex_str:
        return ""
    return (
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
        .replace(r"\dot", "̇")
        .replace(r"\ddot", "̈")
        .replace(r"\\", "\n")
        .replace(r"$$", "")
        .replace(r"$", "")
    )

class EquationDisplay(Static):
    """Widget that renders LaTeX equations as beautiful Unicode or pretty-printed SymPy math."""
    
    DEFAULT_CSS = """
    EquationDisplay {
        width: 100%;
        height: auto;
        margin: 1 0;
        background: $panel;
        border: round $accent;
        content-align: center center;
    }
    """

    def __init__(self, latex_str: str, title: Optional[str] = "Formula", **kwargs):
        super().__init__(**kwargs)
        self.latex_str = latex_str
        self.display_title = title

    def set_equation(self, latex_str: str, title: Optional[str] = "Formula") -> None:
        self.latex_str = latex_str
        self.display_title = title
        self.refresh()

    def render(self) -> Panel:
        try:
            from sympy.parsing.latex import parse_latex
            from sympy import pretty
            # Try parsing with sympy
            expr = parse_latex(self.latex_str)
            pretty_text = pretty(expr)
            renderable = Text(pretty_text, style="bold cyan")
        except Exception:
            # Fallback unicode conversion logic
            clean = latex_to_unicode(self.latex_str)
            renderable = Text(clean.strip(), style="bold italic cyan")

        return Panel(
            renderable,
            title=f"[bold magenta]{self.display_title}[/bold magenta]",
            border_style="magenta",
            expand=True
        )
