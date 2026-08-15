"""ConceptTreeWidget: concept graph sidebar display."""

from textual.reactive import reactive
from textual.widgets import Static


class ConceptTreeWidget(Static):
    concepts: reactive[list] = reactive(list)

    def render(self) -> str:
        items = self.concepts
        if not items:
            items = [
                "Calculus",
                "Linear Algebra",
                "Classical Mechanics",
                "Thermodynamics",
                "Quantum Mechanics",
                "Electromagnetism",
                "Differential Equations",
            ]
        lines = ["[bold cyan]Concept Graph:[/bold cyan]"]
        for c in items[:10]:
            name = c.get("name", str(c)) if isinstance(c, dict) else str(c)
            lines.append(f"  • {name}")
        return "\n".join(lines)
