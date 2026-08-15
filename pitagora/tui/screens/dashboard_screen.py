"""DashboardScreen: journey and concept status overview."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


class DashboardScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "📊 Pitagora Dashboard Screen\n\nLearning Journeys:\n  • Algebra Journey (60% complete)\n\nConcept Graph:\n  • Calculus (Mastered)\n  • Linear Algebra (In Progress)",
            id="dashboard-content",
        )
        yield Footer()
