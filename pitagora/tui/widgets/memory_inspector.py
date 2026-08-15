"""MemoryInspectorWidget: real-time memory and knowledge graph state viewer."""

from typing import Any

from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class MemoryInspectorWidget(Static):
    """Real-time memory and knowledge graph state viewer."""

    memory_count: reactive[int] = reactive(0)
    user_level: reactive[str] = reactive("Intermediate")
    recent_memories: reactive[list] = reactive(list)
    graph_nodes: reactive[list] = reactive(list)

    DEFAULT_NODES = [
        ("ψ", "describes", "Quantum State"),
        ("H", "generates", "Time Evolution"),
        ("∫ dx", "defines", "Total Probability"),
    ]

    def render(self) -> RenderableType:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(justify="left", ratio=1)

        # Header summary
        table.add_row(
            Text.assemble(
                ("🧠 Episodic Memory: ", "dim #a6adc8"),
                (f"{self.memory_count} items", "bold #89b4fa"),
                (" | User: ", "dim #a6adc8"),
                (self.user_level, "bold #a6e3a1"),
            )
        )

        table.add_row(Text("─" * 28, style="dim #45475a"))

        # Knowledge Triples
        table.add_row(Text("Knowledge Triples:", style="bold #cba6f7"))
        triples = self.graph_nodes or self.DEFAULT_NODES
        for item in triples[:3]:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                s, p, o = item[0], item[1], item[2]
                triple_text = Text.assemble(
                    ("  • ", "dim #6c7086"),
                    (str(s), "bold #cdd6f4"),
                    (f" ─{p}→ ", "italic #f9e2af"),
                    (str(o), "bold #89b4fa"),
                )
            else:
                triple_text = Text(f"  • {item}", style="dim #cdd6f4")
            table.add_row(triple_text)

        return Panel(
            table,
            title="[bold #89b4fa]Memory & Graph State[/bold #89b4fa]",
            title_align="left",
            border_style="#45475a",
            padding=(0, 1),
        )
