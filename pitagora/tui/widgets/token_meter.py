"""TokenMeterWidget: token velocity indicator."""

from textual.reactive import reactive
from textual.widgets import Static


class TokenMeterWidget(Static):
    tokens_per_sec: reactive[float] = reactive(0.0)

    def render(self) -> str:
        bar_len = min(20, int(self.tokens_per_sec / 50))
        bar = "█" * bar_len + "░" * (20 - bar_len)
        return f"Velocity: [{bar}] {self.tokens_per_sec:.0f} t/s"
