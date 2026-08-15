"""AgentStatusWidget: displays agent status, tokens, cost, and latency."""

from textual.reactive import reactive
from textual.widgets import Static


class AgentStatusWidget(Static):
    agent_name: reactive[str] = reactive("Orchestrator")
    tokens: reactive[int] = reactive(0)
    cost_usd: reactive[float] = reactive(0.0)
    latency_s: reactive[float] = reactive(0.0)
    velocity_tps: reactive[float] = reactive(0.0)

    def render(self) -> str:
        return (
            f"Agent: {self.agent_name} [●]\n"
            f"Tokens: {self.tokens} | Cost: ${self.cost_usd:.4f} | "
            f"Latency: {self.latency_s:.1f}s | Vel: {self.velocity_tps:.0f} t/s"
        )
