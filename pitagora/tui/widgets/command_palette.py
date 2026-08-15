"""CommandPaletteWidget: interactive slash command palette overlay."""

from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class CommandPaletteWidget(Static):
    """Slash command palette overlay with categorized autocomplete."""

    command_query: reactive[str] = reactive("")

    COMMANDS = [
        ("/explore <topic>", "Start interactive curriculum journey", "Study"),
        ("/verify <expr>", "Symbolic math verification via SymPy", "Math"),
        ("/latex <expr>", "Convert LaTeX equation to Unicode", "Math"),
        ("/mode <mode>", "Switch mode (study / explore / reason / verify)", "Session"),
        ("/topic <topic>", "Change current active topic", "Session"),
        ("/model <model>", "Switch active LLM model/provider", "Model"),
        ("/research <q>", "Autonomous multi-source web research", "Research"),
        ("/quiz", "Generate a practice problem with progressive hints", "Study"),
        ("/progress", "Show concept mastery and learning progress", "Progress"),
        ("/journeys", "List and manage saved learning journeys", "Progress"),
        ("/dashboard", "Visual knowledge map and statistics", "View"),
        ("/save", "Save current chat session state", "Session"),
        ("/sessions", "List past conversation sessions", "Session"),
        ("/resume [id]", "Resume a previous session", "Session"),
        ("/rate <1-5>", "Rate response to train the feedback loop", "Feedback"),
        ("/clear", "Clear conversation buffer", "View"),
        ("/help", "Show all command references and shortcuts", "Help"),
        ("/quit", "Exit Pitagora application", "App"),
    ]

    def render(self) -> RenderableType:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(justify="left", ratio=3)
        table.add_column(justify="left", ratio=5)
        table.add_column(justify="right", ratio=2)

        q = self.command_query.lower()
        matching = [
            c
            for c in self.COMMANDS
            if not q or q in c[0].lower() or q in c[1].lower() or q in c[2].lower()
        ]

        if not matching:
            return Panel(
                Text("No matching slash commands found.", style="italic #f38ba8"),
                title="[bold #89b4fa]Command Palette[/bold #89b4fa]",
                border_style="#45475a",
                padding=(0, 1),
            )

        for cmd, desc, cat in matching[:7]:
            table.add_row(
                Text(cmd, style="bold #89b4fa"),
                Text(desc, style="#cdd6f4"),
                Text(f"[{cat}]", style="dim #cba6f7"),
            )

        return Panel(
            table,
            title="[bold #89b4fa]⚡ Slash Commands[/bold #89b4fa]",
            title_align="left",
            border_style="#89b4fa",
            padding=(0, 1),
        )

