"""PlotScreen: full-screen interactive math & physics plotting screen."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header

from pitagora.tui.widgets.interactive_plot import InteractivePlotWidget


class PlotScreen(Screen):
    """Full-screen interactive plotting workspace with PlotextPlot integration."""

    def __init__(
        self,
        plot_type: str = "quantum_ho",
        quantum_n: int = 0,
        custom_expr: str = "",
        title: str = "Interactive Plot Workspace",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.plot_type = plot_type
        self.quantum_n = quantum_n
        self.custom_expr = custom_expr
        self.plot_title = title

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="plot-workspace"):
            yield InteractivePlotWidget(
                plot_type=self.plot_type,
                quantum_n=self.quantum_n,
                custom_expr=self.custom_expr,
                title=self.plot_title,
                id="interactive-plot",
            )
        yield Footer()
