"""Interactive textual-plotext plotting widget for Pitagora TUI."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Label, Static

try:
    from textual_plotext import PlotextPlot
    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False
    PlotextPlot = None


class InteractivePlotWidget(Widget):
    """Interactive math and physics plotting widget embedded in the TUI."""

    DEFAULT_CSS = """
    InteractivePlotWidget {
        height: 24;
        margin: 1 0;
        background: #1e1e2e;
        border: round #89b4fa;
        padding: 0 1;
        layout: vertical;
    }
    
    #plot-header {
        height: 1;
        margin-bottom: 0;
    }
    
    #plot-canvas {
        height: 18;
        background: #181825;
    }
    
    #plot-toolbar {
        height: 3;
        align: center middle;
        background: #11111b;
        margin-top: 0;
        padding: 0 1;
    }
    
    #plot-toolbar Button {
        margin: 0 1;
        min-width: 10;
        height: 1;
        border: none;
        background: #313244;
        color: #cdd6f4;
    }
    
    #plot-toolbar Button:hover {
        background: #89b4fa;
        color: #11111b;
    }
    
    #plot-toolbar Button.-active {
        background: #a6e3a1;
        color: #11111b;
    }
    """

    BINDINGS = [
        Binding("+", "zoom_in", "Zoom In", show=False),
        Binding("-", "zoom_out", "Zoom Out", show=False),
        Binding("1", "set_state_1", "n=1", show=False),
        Binding("2", "set_state_2", "n=2", show=False),
        Binding("3", "set_state_3", "n=3", show=False),
        Binding("4", "set_state_4", "n=4", show=False),
        Binding("p", "toggle_potential", "Toggle Potential", show=False),
    ]

    plot_type: reactive[str] = reactive("quantum_ho")
    quantum_n: reactive[int] = reactive(0)
    x_min: reactive[float] = reactive(-5.0)
    x_max: reactive[float] = reactive(5.0)
    show_potential: reactive[bool] = reactive(True)
    custom_expr: reactive[str] = reactive("")

    def __init__(
        self,
        plot_type: str = "quantum_ho",
        quantum_n: int = 0,
        x_range: tuple[float, float] = (-5.0, 5.0),
        custom_expr: str = "",
        title: str = "Wavefunction & Probability Density",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.plot_type = plot_type
        self.quantum_n = quantum_n
        self.x_min, self.x_max = x_range
        self.custom_expr = custom_expr
        self.plot_title = title

    def compose(self) -> ComposeResult:
        yield Static(Text(f"📊 {self.plot_title}", style="bold #89b4fa"), id="plot-header")
        if HAS_PLOTEXT and PlotextPlot is not None:
            yield PlotextPlot(id="plot-canvas")
            with Horizontal(id="plot-toolbar"):
                yield Button("n=0", id="btn-n0")
                yield Button("n=1", id="btn-n1")
                yield Button("n=2", id="btn-n2")
                yield Button("n=3", id="btn-n3")
                yield Button("Zoom In (+)", id="btn-zoom-in")
                yield Button("Zoom Out (-)", id="btn-zoom-out")
                yield Button("Reset View", id="btn-reset")
        else:
            yield Static(
                "PlotextPlot unavailable. Install with `pip install textual-plotext` or `pip install pitagora[tui]`.",
                id="plot-canvas",
            )

    def on_mount(self) -> None:
        if HAS_PLOTEXT:
            self.render_plot()

    def watch_quantum_n(self, old_val: int, new_val: int) -> None:
        self.render_plot()

    def watch_x_min(self, old_val: float, new_val: float) -> None:
        self.render_plot()

    def watch_x_max(self, old_val: float, new_val: float) -> None:
        self.render_plot()

    def watch_show_potential(self, old_val: bool, new_val: bool) -> None:
        self.render_plot()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-n0":
            self.quantum_n = 0
        elif button_id == "btn-n1":
            self.quantum_n = 1
        elif button_id == "btn-n2":
            self.quantum_n = 2
        elif button_id == "btn-n3":
            self.quantum_n = 3
        elif button_id == "btn-zoom-in":
            self.action_zoom_in()
        elif button_id == "btn-zoom-out":
            self.action_zoom_out()
        elif button_id == "btn-reset":
            self.x_min = -5.0
            self.x_max = 5.0

    def action_zoom_in(self) -> None:
        span = (self.x_max - self.x_min) * 0.2
        if span > 0.5:
            self.x_min += span / 2
            self.x_max -= span / 2

    def action_zoom_out(self) -> None:
        span = (self.x_max - self.x_min) * 0.25
        self.x_min -= span
        self.x_max += span

    def action_set_state_1(self) -> None:
        self.quantum_n = 1

    def action_set_state_2(self) -> None:
        self.quantum_n = 2

    def action_set_state_3(self) -> None:
        self.quantum_n = 3

    def action_set_state_4(self) -> None:
        self.quantum_n = 4

    def action_toggle_potential(self) -> None:
        self.show_potential = not self.show_potential

    def _compute_quantum_ho_wavefunction(self, x: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute Harmonic Oscillator wavefunction psi_n(x), density |psi_n(x)|^2, and potential V(x)."""
        if n == 0:
            H = np.ones_like(x)
        elif n == 1:
            H = 2 * x
        elif n == 2:
            H = 4 * x**2 - 2
        elif n == 3:
            H = 8 * x**3 - 12 * x
        elif n == 4:
            H = 16 * x**4 - 48 * x**2 + 12
        else:
            coeff = [0] * n + [1]
            H = np.polynomial.hermite.hermval(x, coeff)

        norm = 1.0 / math.sqrt((2**n) * math.factorial(n) * math.sqrt(math.pi))
        psi = norm * np.exp(-(x**2) / 2.0) * H
        density = psi**2
        V = 0.5 * x**2
        return psi, density, V

    def render_plot(self) -> None:
        """Render function plot onto the Plotext canvas."""
        try:
            plot_canvas = self.query_one(PlotextPlot)
        except Exception:
            return

        plt = plot_canvas.plt
        plt.clf()
        plt.theme("dark")

        x_vals = np.linspace(self.x_min, self.x_max, 120)

        if self.plot_type == "quantum_ho" or self.plot_type.startswith("quantum"):
            n = self.quantum_n
            psi, density, V = self._compute_quantum_ho_wavefunction(x_vals, n)
            energy = n + 0.5

            plt.title(f"Quantum Harmonic Oscillator State n={n} (E_{n} = {energy:.1f} ħω)")
            plt.plot(x_vals.tolist(), density.tolist(), label=f"|ψ_{n}(x)|² (Prob. Density)", color="green")
            plt.plot(x_vals.tolist(), psi.tolist(), label=f"ψ_{n}(x) (Wavefunction)", color="cyan")
            if self.show_potential:
                v_scaled = 0.1 * V
                plt.plot(x_vals.tolist(), v_scaled.tolist(), label="V(x) = ½x² (scaled)", color="yellow")
            plt.xlabel("Position x (dimensionless)")
            plt.ylabel("Amplitude / Density")

        elif self.plot_type == "custom" and self.custom_expr:
            try:
                import sympy as sp
                x_sym = sp.Symbol("x")
                expr = sp.sympify(self.custom_expr)
                f_lamb = sp.lambdify(x_sym, expr, modules=["numpy", "math"])
                y_vals = []
                for x in x_vals:
                    try:
                        y_vals.append(float(f_lamb(x)))
                    except Exception:
                        y_vals.append(float("nan"))

                clean_x = [x for x, y in zip(x_vals, y_vals, strict=False) if not math.isnan(y)]
                clean_y = [y for y in y_vals if not math.isnan(y)]

                plt.title(f"Function: y = {self.custom_expr}")
                plt.plot(clean_x, clean_y, label=f"y = {self.custom_expr}", color="cyan")
                plt.xlabel("x")
                plt.ylabel("y")
            except Exception as err:
                plt.title(f"Plot Error: {err}")
        else:
            # Default Wave packet
            k = 3.0
            sigma = 1.2
            packet = np.exp(-((x_vals) ** 2) / (2 * sigma**2)) * np.cos(k * x_vals)
            density = np.exp(-((x_vals) ** 2) / (sigma**2))
            plt.title("Wave Packet & Localization |ψ(x)|²")
            plt.plot(x_vals.tolist(), packet.tolist(), label="Re[ψ(x)] (Wave)", color="cyan")
            plt.plot(x_vals.tolist(), density.tolist(), label="|ψ(x)|² (Envelope)", color="green")
            plt.xlabel("x")
            plt.ylabel("Amplitude")

        plot_canvas.refresh()
