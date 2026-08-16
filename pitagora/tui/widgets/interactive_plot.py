"""InlinePlotCard and InteractivePlotWidget for Pitagora TUI.

Provides first-class interactive math and physics plotting widget embedded directly
into chat messages with dedicated layout boundaries, HD Braille rendering, and client-side
interactive parameter buttons.
"""

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
from textual.widgets import Button, Static

from pitagora.latex_render import latex_to_unicode
from pitagora.tui.events import DisplayPlot

try:
    from textual_plotext import PlotextPlot
    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False
    PlotextPlot = None


class InlinePlotCard(Widget):
    """First-class chat card widget embedding an interactive PlotextPlot and control toolbar."""

    DEFAULT_CSS = """
    InlinePlotCard {
        height: 22;
        width: 100%;
        margin: 1 0;
        background: #1e1e2e;
        border: round #7aa2f7;
        padding: 0 1;
        layout: vertical;
    }

    #plot-card-header {
        height: 1;
        margin-bottom: 0;
    }

    #plot-card-formula {
        height: 1;
        margin-bottom: 0;
    }

    #plot-card-canvas {
        height: 14;
        background: #181825;
    }

    #plot-card-toolbar {
        height: 3;
        align: center middle;
        background: #11111b;
        margin-top: 0;
        padding: 0 1;
    }

    #plot-card-toolbar Button {
        margin: 0 1;
        min-width: 8;
        height: 1;
        border: none;
        background: #313244;
        color: #cdd6f4;
    }

    #plot-card-toolbar Button:hover {
        background: #7aa2f7;
        color: #11111b;
    }

    #plot-card-toolbar Button.-active {
        background: #a6e3a1;
        color: #11111b;
    }
    """

    plot_type: reactive[str] = reactive("quantum_ho")
    quantum_n: reactive[int] = reactive(0)
    loss_variant: reactive[str] = reactive("mse")
    x_min: reactive[float] = reactive(-5.0)
    x_max: reactive[float] = reactive(5.0)
    show_potential: reactive[bool] = reactive(True)
    custom_expr: reactive[str] = reactive("")
    plot_title: reactive[str] = reactive("Wavefunction & Probability Density")
    math_formula: reactive[str] = reactive("")
    x_label: reactive[str] = reactive("x")
    y_label: reactive[str] = reactive("y")
    series_data: reactive[list] = reactive(list)

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
        math_formula: str = "",
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
        self.math_formula = math_formula
        self.series_data = series or []

    def compose(self) -> ComposeResult:
        rendered_title = latex_to_unicode(self.plot_title)
        yield Static(Text(f"📊 {rendered_title}", style="bold #7aa2f7"), id="plot-card-header")

        if self.math_formula:
            rendered_math = latex_to_unicode(self.math_formula)
            yield Static(Text(f"📐 Formula: {rendered_math}", style="italic #bb9af7"), id="plot-card-formula")

        if HAS_PLOTEXT and PlotextPlot is not None:
            yield PlotextPlot(id="plot-card-canvas")
            with Horizontal(id="plot-card-toolbar"):
                # Check whether quantum, loss, or generic controls fit
                p_lower = self.plot_type.lower()
                if "loss" in p_lower or "cost" in p_lower:
                    yield Button("MSE", id="btn-mse", classes="-active" if self.loss_variant == "mse" else "")
                    yield Button("MAE", id="btn-mae", classes="-active" if self.loss_variant == "mae" else "")
                    yield Button("Huber", id="btn-huber", classes="-active" if self.loss_variant == "huber" else "")
                else:
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
                id="plot-card-canvas",
            )

    def on_mount(self) -> None:
        if HAS_PLOTEXT:
            self.render_plot()

    def _update_button_states(self) -> None:
        """Update active button styling to reflect current state."""
        try:
            for n_idx in range(4):
                try:
                    btn = self.query_one(f"#btn-n{n_idx}", Button)
                    if n_idx == self.quantum_n:
                        btn.add_class("-active")
                    else:
                        btn.remove_class("-active")
                except Exception:
                    pass

            for loss_id in ("mse", "mae", "huber"):
                try:
                    btn = self.query_one(f"#btn-{loss_id}", Button)
                    if self.loss_variant == loss_id:
                        btn.add_class("-active")
                    else:
                        btn.remove_class("-active")
                except Exception:
                    pass
        except Exception:
            pass

    def watch_quantum_n(self, old_val: int, new_val: int) -> None:
        self._update_button_states()
        self.render_plot()

    def watch_loss_variant(self, old_val: str, new_val: str) -> None:
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
        elif button_id == "btn-mse":
            self.loss_variant = "mse"
        elif button_id == "btn-mae":
            self.loss_variant = "mae"
        elif button_id == "btn-huber":
            self.loss_variant = "huber"
        elif button_id == "btn-toggle-v":
            self.action_toggle_potential()
        elif button_id == "btn-zoom-in":
            self.action_zoom_in()
        elif button_id == "btn-zoom-out":
            self.action_zoom_out()
        elif button_id == "btn-reset":
            self.action_reset()

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

    def action_reset(self) -> None:
        self.x_min = -5.0
        self.x_max = 5.0

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
        """Render high-resolution Braille plot onto the embedded Plotext canvas."""
        try:
            plot_canvas = self.query_one(PlotextPlot)
        except Exception:
            return

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

        if "loss" in self.plot_type.lower() or "cost" in self.plot_type.lower():
            # Loss function curves
            err = x_vals
            if self.loss_variant == "mae":
                loss = np.abs(err)
                name = r"L_{MAE}(e) = |e|"
            elif self.loss_variant == "huber":
                delta = 1.0
                loss = np.where(np.abs(err) <= delta, 0.5 * err**2, delta * (np.abs(err) - 0.5 * delta))
                name = r"L_{Huber}(e, \delta=1)"
            else:
                loss = 0.5 * err**2
                name = r"L_{MSE}(e) = \frac{1}{2} e^2"

            plt.title(f"Loss Function: {self.loss_variant.upper()}")
            plt.plot(err.tolist(), loss.tolist(), label=latex_to_unicode(name), color="cyan", marker="braille")
            plt.xlabel("Error e = y - ŷ")
            plt.ylabel("Loss L(e)")

        elif self.plot_type == "quantum_ho" or self.plot_type.startswith("quantum"):
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


class InteractivePlotWidget(InlinePlotCard):
    """Backward-compatible alias for InlinePlotCard."""
    pass
