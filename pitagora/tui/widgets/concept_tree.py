"""ConceptTreeWidget: concept graph sidebar display."""

from textual.reactive import reactive
from textual.widgets import Static


class ConceptTreeWidget(Static):
    concepts: reactive[list] = reactive(list)

    def render(self) -> str:
        if not self.concepts:
            return "Concept Graph:\n  • (No concepts loaded)"
        lines = ["Concept Graph:"]
        for c in self.concepts[:10]:
            name = c.get("name", str(c)) if isinstance(c, dict) else str(c)
            lines.append(f"  • {name}")
        return "\n".join(lines)
