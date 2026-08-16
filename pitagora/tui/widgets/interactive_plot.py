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

from pitagora.tui.events import DisplayPlot

try:
    from textual_plotext import PlotextPlot
    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False
    PlotextPlot = None


class InteractivePlotWidget(Widget):
    """Interactive math and physics plotting widget with HD Braille rendering."""

    DEFAULT_CSS = """
    InteractivePlotWidget {
        height: 24;
        margin: 1 0;
        background: #1e1e2e;
        border: round #7aa2f7;
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
        min-width: 8;
        height: 1;
        border: none;
        background: #313244;
        color: #cdd6f4;
    }
    
    #plot-toolbar Button:hover {
        background: #7aa2f7;
        color: #11111b;
    }
    
    #plot-toolbar Button.-active {
        background: #7dcfff;
        color: #11111b;
    }
    """

    BINDINGS = [
        Binding("+", "zoom_in", "Zoom In", show=False),
        Binding("-", "zoom_out", "Zoom Out", show=False),
        Binding("0", "set_state_0", "n=0", show=False),
        Binding("1", "set_state_1", "n=1", show=False),
        Binding("2", "set_state_2", "n=2", show=False),
        Binding("3", "set_state_3", "n=3", show=False),
        Binding("p", "toggle_potential", "Toggle Potential", show=False),
    ]

    plot_type: reactive[str] = reactive("quantum_ho")
    quantum_n: reactive[int] = reactive(0)
    x_min: reactive[float] = reactive(-5.0)
    x_max: reactive[float] = reactive(5.0)
    show_potential: reactive[bool] = reactive(True)
    custom_expr: reactive[str] = reactive("")
    plot_title: reactive[str] = reactive("Wavefunction & Probability Density")
    x_label: reactive[str] = reactive("x")
    y_label: reactive[str] = reactive("y")
    series_data: reactive[list] = reactive(list)

    # Theme palette aligned with Pitagora dark / Tokyo Night / Catppuccin
    THEME_COLORS = ["#7dcfff", "#bb9af7", "#7aa2f7", "#9ece6a", "#e0af68", "#f7768e"]

    def __init__(
        self,
        plot_type: str = "quantum_ho",
        quantum_n: int = 0,
        x_range: tuple[float, float] = (-5.0, 5.0),
        custom_expr: str = "",
        title: str = "Wavefunction & Probability Density",
        series: list[dict] | None = None,
        x_label: str = "x",
        y_label: str = "y",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.plot_type = plot_type
        self.quantum_n = quantum_n
        self.x_min, self.x_max = x_range
        self.custom_expr = custom_expr
        self.plot_title = title
        self.x_label = x_label
        self.y_label = y_label
        self.series_data = series or []

    def compose(self) -> ComposeResult:
        yield Static(Text(f"📊 {self.plot_title}", style="bold #7aa2f7"), id="plot-header")
        if HAS_PLOTEXT and PlotextPlot is not None:
            yield PlotextPlot(id="plot-canvas")
            with Horizontal(id="plot-toolbar"):
                yield Button("n=0", id="btn-n0", classes="-active" if self.quantum_n == 0 else "")
                yield Button("n=1", id="btn-n1", classes="-active" if self.quantum_n == 1 else "")
                yield Button("n=2", id="btn-n2", classes="-active" if self.quantum_n == 2 else "")
                yield Button("n=3", id="btn-n3", classes="-active" if self.quantum_n == 3 else "")
                yield Button("V(x)", id="btn-toggle-v")
                yield Button("Zoom +", id="btn-zoom-in")
                yield Button("Zoom -", id="btn-zoom-out")
                yield Button("Reset", id="btn-reset")
        else:
            yield Static(
                "PlotextPlot unavailable. Install with `pip install textual-plotext` or `pip install pitagora[tui]`.",
                id="plot-canvas",
            )

    def on_mount(self) -> None:
        if HAS_PLOTEXT:
            self.render_plot()

    def on_display_plot(self, event: DisplayPlot) -> None:
        """Handle DisplayPlot event dispatched by LLM tool or sub-agent."""
        self.plot_title = event.title
        self.plot_type = event.plot_type
        self.x_label = event.x_label
        self.y_label = event.y_label
        self.series_data = event.series
        if hasattr(event, "quantum_n") and event.quantum_n is not None:
            self.quantum_n = event.quantum_n
        if hasattr(event, "domain") and event.domain and len(event.domain) == 2:
            self.x_min, self.x_max = float(event.domain[0]), float(event.domain[1])
        if event.math_formula:
            self.custom_expr = event.math_formula
        try:
            header = self.query_one("#plot-header", Static)
            header.update(Text(f"📊 {self.plot_title}", style="bold #7aa2f7"))
        except Exception:
            pass
        self._update_button_states()
        self.render_plot()

    def _update_button_states(self) -> None:
        """Update active button styling to reflect current state."""
        try:
            for n_idx in range(4):
                btn = self.query_one(f"#btn-n{n_idx}", Button)
                if n_idx == self.quantum_n:
                    btn.add_class("-active")
                else:
                    btn.remove_class("-active")
        except Exception:
            pass

    def watch_quantum_n(self, old_val: int, new_val: int) -> None:
        self._update_button_states()
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
        elif button_id == "btn-toggle-v":
            self.action_toggle_potential()
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

    def action_set_state_0(self) -> None:
        self.quantum_n = 0

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
        """Render high-resolution Braille plot onto the Plotext canvas."""
        try:
            plot_canvas = self.query_one(PlotextPlot)
        except Exception:
            return

        from pitagora.latex_render import latex_to_unicode

        plt = plot_canvas.plt
        plt.clf()
        plt.theme("dark")
        plt.grid(True, True)

        # 1. Custom structured series plotting from tool call or PlotArchitect payload
        if self.series_data:
            plt.title(latex_to_unicode(self.plot_title))
            plt.xlabel(latex_to_unicode(self.x_label))
            plt.ylabel(latex_to_unicode(self.y_label))
            colors = ["cyan", "magenta", "blue", "green", "yellow", "red"]
            for idx, s in enumerate(self.series_data):
                x = s.get("x", [])
                y = s.get("y", [])
                raw_name = s.get("name", f"Series {idx+1}")
                name = latex_to_unicode(raw_name)
                color = colors[idx % len(colors)]
                p_type = self.plot_type.lower()
                if p_type == "scatter":
                    plt.scatter(x, y, label=name, color=color, marker="braille")
                elif p_type == "bar":
                    plt.bar(x, y, label=name, color=color)
                else:
                    plt.plot(x, y, label=name, color=color, marker="braille")
            plot_canvas.refresh()
            return

        # 2. Preset or mathematical function plotting
        x_vals = np.linspace(self.x_min, self.x_max, 140)

        if self.plot_type == "quantum_ho" or self.plot_type.startswith("quantum"):
            n = self.quantum_n
            psi, density, V = self._compute_quantum_ho_wavefunction(x_vals, n)
            energy = n + 0.5

            plt.title(f"Quantum Harmonic Oscillator n={n} (E={energy:.1f} ħω)")
            plt.plot(x_vals.tolist(), density.tolist(), label=f"|ψ_{n}(x)|² (Prob. Density)", color="cyan", marker="braille")
            plt.plot(x_vals.tolist(), psi.tolist(), label=f"ψ_{n}(x) (Wavefunction)", color="magenta", marker="braille")
            if self.show_potential:
                v_scaled = 0.1 * V
                plt.plot(x_vals.tolist(), v_scaled.tolist(), label="V(x) = ½x² (Potential)", color="yellow", marker="braille")
            plt.xlabel("Position x")
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

                rendered_expr = latex_to_unicode(self.custom_expr)
                plt.title(f"y = {rendered_expr}")
                plt.plot(clean_x, clean_y, label=f"y = {rendered_expr}", color="cyan", marker="braille")
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
            plt.title("Wave Packet Localization |ψ(x)|²")
            plt.plot(x_vals.tolist(), packet.tolist(), label="Re[ψ(x)] (Wave)", color="cyan", marker="braille")
            plt.plot(x_vals.tolist(), density.tolist(), label="|ψ(x)|² (Envelope)", color="green", marker="braille")
            plt.xlabel("x")
            plt.ylabel("Amplitude")

        plot_canvas.refresh()
