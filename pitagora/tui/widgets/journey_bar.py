"""JourneyBarWidget: dynamic progress bar for active learning journey."""

from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


from pitagora.tui.events import JourneyProgressChanged


class JourneyBarWidget(Static):
    """Dynamic progress indicator for curriculum journey."""

    progress: reactive[float] = reactive(0.0)
    topic: reactive[str] = reactive("General")
    mastered_count: reactive[int] = reactive(0)
    total_count: reactive[int] = reactive(0)

    def on_journey_progress_changed(self, event: JourneyProgressChanged) -> None:
        """Handle JourneyProgressChanged event from the agent state machine."""
        self.topic = event.topic
        self.progress = event.progress
        self.mastered_count = event.mastered_count
        self.total_count = event.total_count
        self.refresh()


    def render(self) -> RenderableType:
        pct = max(0.0, min(1.0, float(self.progress)))
        pct_val = int(pct * 100)

        # 16-segment smooth bar
        bar_len = 16
        filled = int(pct * bar_len)
        bar = "▰" * filled + "▱" * (bar_len - filled)

        # Color based on progress
        if pct >= 0.8:
            color = "#a6e3a1"  # green
            tier = "Mastered"
        elif pct >= 0.4:
            color = "#f9e2af"  # yellow
            tier = "Developing"
        else:
            color = "#89b4fa"  # blue
            tier = "Exploring"

        content = Text.assemble(
            (f"{self.topic}\n", "bold #cdd6f4"),
            (f"[{bar}] ", f"bold {color}"),
            (f"{pct_val}%", f"bold {color}"),
            (f" • {tier}", "dim #a6adc8"),
        )
        if self.total_count > 0:
            content.append(f" ({self.mastered_count}/{self.total_count} concepts)", "dim #6c7086")

        return Panel(
            content,
            title="[bold #89b4fa]Journey Progress[/bold #89b4fa]",
            title_align="left",
            border_style="#45475a",
            padding=(0, 1),
        )

