"""Textual message definitions for Pitagora TUI events."""

from textual.message import Message


class ConceptUpdated(Message):
    """Fired when concepts or active curriculum changes."""

    def __init__(
        self,
        concepts: list,
        active_concept: str = "",
        topic: str = "Curriculum",
    ) -> None:
        super().__init__()
        self.concepts = concepts
        self.active_concept = active_concept
        self.topic = topic


class JourneyProgressChanged(Message):
    """Fired when learning progress or mastery scores update."""

    def __init__(
        self,
        topic: str,
        progress: float,
        mastered_count: int = 0,
        total_count: int = 0,
    ) -> None:
        super().__init__()
        self.topic = topic
        self.progress = progress
        self.mastered_count = mastered_count
        self.total_count = total_count


class DiagnosticsUpdated(Message):
    """Fired when runtime diagnostics or tool verification state updates."""

    def __init__(
        self,
        tokens: int = 0,
        latency_s: float = 0.0,
        cost_usd: float = 0.0,
        velocity_tps: float = 0.0,
        tool_status: str = "idle",
        last_verification: str = "",
    ) -> None:
        super().__init__()
        self.tokens = tokens
        self.latency_s = latency_s
        self.cost_usd = cost_usd
        self.velocity_tps = velocity_tps
        self.tool_status = tool_status
        self.last_verification = last_verification


class DisplayPlot(Message):
    """Fired when an agent or tool generates an interactive plot."""

    def __init__(
        self,
        title: str,
        plot_type: str = "line",
        series: list[dict] | None = None,
        x_label: str = "x",
        y_label: str = "y",
        math_formula: str = "",
        quantum_n: int = 0,
        domain: list[float] | None = None,
    ) -> None:
        super().__init__()
        self.title = title
        self.plot_type = plot_type
        self.series = series or []
        self.x_label = x_label
        self.y_label = y_label
        self.math_formula = math_formula
        self.quantum_n = quantum_n
        self.domain = domain or []
