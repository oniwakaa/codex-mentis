"""JourneyBarWidget: progress bar for learning journey."""

from textual.reactive import reactive
from textual.widgets import Static


class JourneyBarWidget(Static):
    progress: reactive[float] = reactive(0.0)
    topic: reactive[str] = reactive("General")

    def render(self) -> str:
        pct = int(self.progress * 100)
        filled = int(self.progress * 15)
        bar = "▓" * filled + "░" * (15 - filled)
        return f"Journey ({self.topic}): [{bar}] {pct}%"
