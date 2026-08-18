"""DerivationView — interactive step-by-step mathematical & dialectical derivation widget.

Provides a rich visual component for navigating proof and derivation steps in Textual TUI.
Follows ponytail minimalism: pure Textual reactive component with clear separation of concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Static


@dataclass
class DerivationStep:
    """A single mathematical, physical, or logical step in a derivation."""

    step_number: int
    title: str
    equation_latex: str
    justification: str
    annotations: list[str] = field(default_factory=list)


class DerivationView(Widget):
    """Textual widget for displaying and stepping through structured mathematical proofs."""

    DEFAULT_CSS = """
    DerivationView {
        height: auto;
        min-height: 10;
        background: ;
        border: round ;
        padding: 1;
        margin: 1 0;
    }
    .derivation-title {
        text-style: bold;
        color: ;
        padding-bottom: 1;
    }
    .derivation-step-num {
        color: ;
        text-style: bold;
    }
    .derivation-body {
        margin: 1 0;
    }
    .derivation-controls {
        height: 3;
        align: center middle;
    }
    """

    current_step: reactive[int] = reactive(0)

    def __init__(
        self,
        title: str,
        steps: list[DerivationStep] | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.title_text = title
        self.steps = steps or []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"△ Derivation: {self.title_text}", classes="derivation-title", id="deriv_title")
            yield Static("", id="deriv_content", classes="derivation-body")

    def on_mount(self) -> None:
        self._update_display()

    def watch_current_step(self, new_val: int) -> None:
        self._update_display()

    def next_step(self) -> bool:
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            return True
        return False

    def prev_step(self) -> bool:
        if self.current_step > 0:
            self.current_step -= 1
            return True
        return False

    def _update_display(self) -> None:
        if not self.is_mounted:
            return
        content_widget = self.query_one("#deriv_content", Static)
        if not self.steps:
            content_widget.update(Text("No derivation steps loaded.", style="dim"))
            return

        idx = max(0, min(self.current_step, len(self.steps) - 1))
        step = self.steps[idx]

        render_text = Text()
        render_text.append(f"Step {step.step_number} of {len(self.steps)}: ", style="bold cyan")
        render_text.append(f"{step.title}\n\n", style="bold white")

        if step.equation_latex:
            render_text.append("  [Equation]  ", style="bold gold1")
            render_text.append(f"{step.equation_latex}\n\n", style="italic white")

        if step.justification:
            render_text.append("  ▸ Justification: ", style="bold green")
            render_text.append(f"{step.justification}\n", style="dim white")

        if step.annotations:
            render_text.append("\n  Notes:\n", style="bold yellow")
            for a in step.annotations:
                render_text.append(f"    • {a}\n", style="dim white")

        content_widget.update(Panel(render_text, border_style="indigo"))
