"""ConceptTreeWidget: interactive knowledge and journey tree."""

from typing import Any

from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from textual.reactive import reactive
from textual.widgets import Static


from pitagora.tui.events import ConceptUpdated


class ConceptTreeWidget(Static):
    """Visual concept hierarchy indicating visited, active, and recommended topics."""

    concepts: reactive[list] = reactive(list)
    active_concept: reactive[str] = reactive("")
    topic_name: reactive[str] = reactive("Curriculum")

    DEFAULT_CURRICULUM = {
        "Mathematics": [
            {"name": "Calculus & Limits", "status": "mastered", "mastery": 0.95},
            {"name": "Differential Equations", "status": "active", "mastery": 0.60, "prereq": "Calculus"},
            {"name": "Linear Algebra", "status": "recommended", "mastery": 0.30},
            {"name": "Complex Analysis", "status": "locked", "mastery": 0.0, "prereq": "Calculus"},
        ],
        "Physics": [
            {"name": "Classical Mechanics", "status": "mastered", "mastery": 0.85},
            {"name": "Electromagnetism", "status": "active", "mastery": 0.50, "prereq": "Calculus"},
            {"name": "Quantum Mechanics", "status": "recommended", "mastery": 0.20, "prereq": "Linear Algebra"},
            {"name": "Thermodynamics", "status": "locked", "mastery": 0.0},
        ],
    }

    def on_concept_updated(self, event: ConceptUpdated) -> None:
        """Handle dynamic ConceptUpdated message from the agent loop."""
        self.concepts = event.concepts
        if event.active_concept:
            self.active_concept = event.active_concept
        if event.topic:
            self.topic_name = event.topic
        self.refresh()

    def render(self) -> RenderableType:
        root_label = Text.assemble(
            ("📚 ", "bold #89b4fa"),
            (f"{self.topic_name} Graph", "bold #cdd6f4"),
        )
        tree = Tree(root_label)

        if self.concepts:
            # Custom concepts supplied (e.g. from TeachingSession or ConceptGraph)
            for c in self.concepts:
                if isinstance(c, dict):
                    name = c.get("name", "Unknown")
                    status = c.get("status", "recommended")
                    mastery = float(c.get("mastery", 0.0))
                    prereqs = c.get("prerequisites", [])
                else:
                    name = str(c)
                    status = "active" if name == self.active_concept else "recommended"
                    mastery = 0.5
                    prereqs = []

                node_text = self._format_node(name, status, mastery)
                node = tree.add(node_text)
                for pr in prereqs:
                    node.add(Text(f"↳ req: {pr}", style="dim #a6adc8"))
        else:
            # Standard domain hierarchy
            for domain, items in self.DEFAULT_CURRICULUM.items():
                domain_node = tree.add(Text(f"📁 {domain}", style="bold #cba6f7"))
                for item in items:
                    name = item["name"]
                    status = "active" if name == self.active_concept else item["status"]
                    node_text = self._format_node(name, status, item["mastery"])
                    child = domain_node.add(node_text)
                    if "prereq" in item:
                        child.add(Text(f"↳ req: {item['prereq']}", style="dim #6c7086"))

        return Panel(
            tree,
            title="[bold #89b4fa]Knowledge Tree[/bold #89b4fa]",
            title_align="left",
            border_style="#45475a",
            padding=(0, 1),
        )


    def _format_node(self, name: str, status: str, mastery: float) -> Text:
        pct_str = f"[{int(mastery * 100)}%]" if mastery > 0 else ""
        if status == "mastered" or mastery >= 0.8:
            return Text.assemble(
                ("✓ ", "bold #a6e3a1"),
                (name, "#a6e3a1"),
                (f" {pct_str}", "dim #a6e3a1"),
            )
        elif status == "active":
            return Text.assemble(
                ("▸ ", "bold #89b4fa"),
                (name, "bold #89b4fa"),
                (f" {pct_str}", "bold #89b4fa"),
                (" (active)", "italic #74c7ec"),
            )
        elif status == "recommended":
            return Text.assemble(
                ("→ ", "bold #f9e2af"),
                (name, "#f9e2af"),
                (" (next)", "dim #f9e2af"),
            )
        else:
            return Text.assemble(
                ("• ", "dim #6c7086"),
                (name, "dim #6c7086"),
            )

