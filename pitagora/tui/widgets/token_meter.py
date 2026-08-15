"""TokenMeterWidget: token generation velocity indicator."""

from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class TokenMeterWidget(Static):
    """Real-time token generation velocity meter."""

    tokens_per_sec: reactive[float] = reactive(0.0)
    peak_tps: reactive[float] = reactive(0.0)

    def render(self) -> RenderableType:
        tps = max(0.0, float(self.tokens_per_sec))
        if tps > self.peak_tps:
            self.peak_tps = tps

        # Bar out of 60 t/s
        bar_len = 16
        filled = min(bar_len, int((tps / 60.0) * bar_len))
        bar = "█" * filled + "░" * (bar_len - filled)

        # Color based on speed
        if tps >= 40:
            color = "#a6e3a1"  # green
            desc = "Fast"
        elif tps >= 15:
            color = "#89b4fa"  # blue
            desc = "Normal"
        elif tps > 0:
            color = "#f9e2af"  # yellow
            desc = "Slow"
        else:
            color = "#6c7086"  # dim
            desc = "Idle"

        content = Text.assemble(
            (f"[{bar}] ", f"bold {color}"),
            (f"{tps:.1f} t/s", f"bold {color}"),
            (f" • {desc}", "dim #a6adc8"),
        )

        return Panel(
            content,
            title="[bold #89b4fa]Token Velocity[/bold #89b4fa]",
            title_align="left",
            border_style="#45475a",
            padding=(0, 1),
        )

