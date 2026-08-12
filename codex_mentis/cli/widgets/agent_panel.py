from typing import Dict, Any, List
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static, Label, DataTable
from textual.widget import Widget
from rich.text import Text

class AgentPanel(Widget):
    """
    A widget that displays the status of active agents, their reasoning steps,
    confidence levels, and tools in use.
    """
    
    DEFAULT_CSS = """
    AgentPanel {
        width: 100%;
        height: 100%;
        layout: vertical;
        border: solid $accent;
    }
    
    #panel-title {
        height: 3;
        background: $boost;
        content-align: center center;
        text-style: bold;
        border-bottom: solid $accent;
    }
    
    DataTable {
        height: 1fr;
        background: $background;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.agents_state: Dict[str, Dict[str, Any]] = {
            "Tutor": {"state": "Idle", "tool": "None", "confidence": 1.0, "thoughts": "Awaiting question..."},
            "Researcher": {"state": "Idle", "tool": "None", "confidence": 1.0, "thoughts": "Awaiting inquiry..."},
            "Prover": {"state": "Idle", "tool": "None", "confidence": 1.0, "thoughts": "Awaiting deduction..."},
            "Reviewer": {"state": "Idle", "tool": "None", "confidence": 1.0, "thoughts": "Awaiting validation..."},
            "Visualizer": {"state": "Idle", "tool": "None", "confidence": 1.0, "thoughts": "Awaiting expression..."},
        }

    def compose(self) -> ComposeResult:
        yield Label("COLLABORATIVE AGENTS MONITOR", id="panel-title")
        table = DataTable(id="agent-table")
        table.cursor_type = "row"
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#agent-table", DataTable)
        table.add_columns("Agent Name", "State", "Active Tool", "Confidence", "Thoughts / Actions")
        self.refresh_table()

    def update_agent(
        self, 
        name: str, 
        state: str, 
        tool: str = "None", 
        confidence: float = 1.0, 
        thoughts: str = ""
    ) -> None:
        """Update state for a single agent and refresh the UI."""
        normalized_name = name.title().strip()
        if normalized_name in self.agents_state:
            self.agents_state[normalized_name] = {
                "state": state,
                "tool": tool,
                "confidence": confidence,
                "thoughts": thoughts
            }
            self.refresh_table()

    def set_all_idle(self) -> None:
        """Set all agents back to idle state."""
        for name in self.agents_state:
            self.agents_state[name]["state"] = "Idle"
            self.agents_state[name]["tool"] = "None"
            self.agents_state[name]["thoughts"] = "Awaiting request..."
        self.refresh_table()

    def refresh_table(self) -> None:
        """Repopulate rows in the data table."""
        try:
            table = self.query_one("#agent-table", DataTable)
        except Exception:
            return # Widget not fully mounted/composed yet
            
        table.clear()
        
        for name, info in self.agents_state.items():
            state = info["state"]
            tool = info["tool"]
            conf = info["confidence"]
            thoughts = info["thoughts"]
            
            # Format state with color
            if state == "Thinking":
                state_text = Text(state, style="bold orange1")
            elif state == "Working":
                state_text = Text(state, style="bold cyan")
            else:
                state_text = Text(state, style="dim white")
                
            # Format tool
            tool_text = Text(tool, style="magenta" if tool != "None" else "dim")
            
            # Format confidence
            if conf >= 0.8:
                conf_style = "bold green"
            elif conf >= 0.5:
                conf_style = "bold yellow"
            else:
                conf_style = "bold red"
            conf_text = Text(f"{conf * 100:.0f}%", style=conf_style)
            
            # Format thoughts
            thoughts_text = Text(thoughts, style="italic")
            
            table.add_row(
                Text(name, style="bold white"),
                state_text,
                tool_text,
                conf_text,
                thoughts_text
            )
