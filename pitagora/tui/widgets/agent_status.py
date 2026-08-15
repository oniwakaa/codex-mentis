"""AgentStatusWidget: displays provider diagnostics, latency, tokens, and tool status."""

from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


from pitagora.tui.events import DiagnosticsUpdated


class AgentStatusWidget(Static):
    """Provider & Runtime Diagnostics and Tool Status."""

    agent_name: reactive[str] = reactive("Orchestrator")
    provider: reactive[str] = reactive("OpenAI (GPT-4o)")
    model: reactive[str] = reactive("gpt-4o")
    tokens: reactive[int] = reactive(0)
    cost_usd: reactive[float] = reactive(0.0)
    latency_s: reactive[float] = reactive(0.0)
    velocity_tps: reactive[float] = reactive(0.0)
    tool_status: reactive[str] = reactive("idle")
    tool_name: reactive[str] = reactive("SymPy Sandbox")
    last_verification: reactive[str] = reactive("Ready")

    def on_diagnostics_updated(self, event: DiagnosticsUpdated) -> None:
        """Handle DiagnosticsUpdated event from agent runtime."""
        self.tokens = event.tokens
        self.latency_s = event.latency_s
        self.cost_usd = event.cost_usd
        self.velocity_tps = event.velocity_tps
        self.tool_status = event.tool_status
        if event.last_verification:
            self.last_verification = event.last_verification
        self.refresh()


    def render(self) -> RenderableType:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(justify="left", ratio=1)
        table.add_column(justify="right", ratio=1)

        # Provider & Model
        table.add_row(
            Text.assemble(("Provider: ", "dim #a6adc8"), (self.provider, "bold #89b4fa")),
            Text.assemble(("Model: ", "dim #a6adc8"), (self.model, "bold #cdd6f4")),
        )

        # Agent role & Latency
        latency_str = f"{self.latency_s * 1000:.0f}ms" if self.latency_s < 1.0 else f"{self.latency_s:.2f}s"
        table.add_row(
            Text.assemble(("Agent: ", "dim #a6adc8"), (self.agent_name, "bold #a6e3a1")),
            Text.assemble(("Latency: ", "dim #a6adc8"), (latency_str, "bold #f9e2af")),
        )

        # Tokens & Cost
        table.add_row(
            Text.assemble(("Tokens: ", "dim #a6adc8"), (f"{self.tokens:,}", "#cdd6f4")),
            Text.assemble(("Cost: ", "dim #a6adc8"), (f"${self.cost_usd:.4f}", "bold #a6e3a1")),
        )

        # Tool & Verification badge
        tool_colors = {
            "idle": "#6c7086",
            "running": "#f9e2af",
            "success": "#a6e3a1",
            "error": "#f38ba8",
        }
        tool_color = tool_colors.get(self.tool_status.lower(), "#89b4fa")
        tool_icon = {"idle": "⚪", "running": "⏳", "success": "✓", "error": "✗"}.get(
            self.tool_status.lower(), "⚙️"
        )

        table.add_row(
            Text.assemble(
                ("Tool: ", "dim #a6adc8"),
                (f"{self.tool_name} ", "bold #cdd6f4"),
            ),
            Text.assemble(
                (f"{tool_icon} {self.tool_status.upper()}", f"bold {tool_color}"),
            ),
        )

        return Panel(
            table,
            title="[bold #89b4fa]Runtime Diagnostics[/bold #89b4fa]",
            title_align="left",
            border_style="#45475a",
            padding=(0, 1),
        )

