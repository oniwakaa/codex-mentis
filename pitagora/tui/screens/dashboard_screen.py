"""DashboardScreen: dynamic journey and concept status overview."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from pitagora.concepts.tracker import MasteryTracker
from pitagora.journeys.store import list_journeys


class DashboardScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._build_dashboard_content(), id="dashboard-content")
        yield Footer()

    def on_screen_resume(self) -> None:
        static = self.query_one("#dashboard-content", Static)
        static.update(self._build_dashboard_content())

    def _build_dashboard_content(self) -> str:
        lines = ["📊 [bold cyan]Pitagora Learning Dashboard[/bold cyan]\n"]

        # Active journeys
        journeys = list_journeys()
        lines.append("[bold]Active Learning Journeys:[/bold]")
        if journeys:
            for j in journeys[:5]:
                topic = j.get("topic", "Unknown")
                status = j.get("status", "in_progress")
                count = j.get("interaction_count", 0)
                lines.append(f"  • {topic} — {status} ({count} interactions)")
        else:
            lines.append("  • (No active journeys. Start one with /explore <topic>)")

        lines.append("\n[bold]Concept Mastery Overview:[/bold]")
        try:
            tracker = MasteryTracker()
            strong = tracker.get_strong_areas()
            weak = tracker.get_weak_areas()
            progress = tracker.get_overall_progress()

            lines.append(f"  Overall Progress: {progress * 100:.1f}%\n")
            if strong:
                lines.append(
                    "  [green]Strong Areas:[/green] "
                    + ", ".join(s.get("concept", "") for s in strong[:5])
                )
            if weak:
                lines.append(
                    "  [yellow]Areas to Review:[/yellow] "
                    + ", ".join(w.get("concept", "") for w in weak[:5])
                )
            if not strong and not weak:
                lines.append("  • Concepts will appear as you study and practice.")
        except Exception:
            lines.append("  • Concept tracker initializing...")

        return "\n".join(lines)
