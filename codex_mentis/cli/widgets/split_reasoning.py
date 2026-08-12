import re
from typing import Tuple
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.widget import Widget
from textual.widgets import Markdown, Static, Label
from rich.panel import Panel
from rich.text import Text

class SplitReasoning(Widget):
    """
    A side-by-side panel widget that shows mathematical derivation steps on the left 
    and intuitive explanation on the right with synchronized scrolling.
    """
    
    DEFAULT_CSS = """
    SplitReasoning {
        width: 100%;
        height: 100%;
        layout: vertical;
        border: double $accent;
    }
    
    #header-bar {
        height: 3;
        width: 100%;
        background: $panel;
        layout: horizontal;
    }
    
    #header-bar Label {
        width: 50%;
        text-align: center;
        content-align: center center;
        text-style: bold;
        background: $boost;
        border-bottom: solid $accent;
    }
    
    #panels-container {
        width: 100%;
        height: 1fr;
        layout: horizontal;
    }
    
    .scroll-pane {
        width: 50%;
        height: 100%;
        scrollbar-gutter: stable;
    }
    
    #left-pane {
        border-right: tall $accent;
    }
    
    #left-pane Markdown, #right-pane Markdown {
        padding: 1 2;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.derivation_md = "# Mathematical Derivation\n*No derivation loaded yet.*"
        self.intuition_md = "# Physical Intuition\n*No intuition loaded yet.*"

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label("DERIVATION & CALCULUS"),
            Label("CONCEPTUAL INTUITION"),
            id="header-bar"
        )
        yield Horizontal(
            ScrollableContainer(Markdown(self.derivation_md, id="derivation-content"), id="left-pane", classes="scroll-pane"),
            ScrollableContainer(Markdown(self.intuition_md, id="intuition-content"), id="right-pane", classes="scroll-pane"),
            id="panels-container"
        )

    def set_content(self, derivation: str, intuition: str) -> None:
        """Explicitly set both sides of the reasoning pane."""
        self.derivation_md = derivation
        self.intuition_md = intuition
        
        self.query_one("#derivation-content", Markdown).update(self.derivation_md)
        self.query_one("#intuition-content", Markdown).update(self.intuition_md)

    def split_and_set_text(self, full_text: str) -> None:
        """Parses unified text containing both formal and conceptual sections."""
        derivation, intuition = self._parse_split_text(full_text)
        self.set_content(derivation, intuition)

    def _parse_split_text(self, text: str) -> Tuple[str, str]:
        """Tries to split standard multi-agent response into mathematical vs intuitive parts."""
        # Check common section headers
        deriv_headers = [
            "### Rigorous Mathematical Derivation", 
            "### 2. Derived Proof & Calculus", 
            "### 1. Mathematical Derivation"
        ]
        int_headers = [
            "### Conceptual & Intuitive Breakdown", 
            "### 3. Mathematical Audit & Critique", 
            "### 1. Research Background & Equations"
        ]
        
        deriv_parts = []
        int_parts = []
        
        current_dest = "both"
        
        lines = text.splitlines()
        for line in lines:
            # Check headers
            if any(h in line for h in deriv_headers):
                current_dest = "deriv"
                continue
            elif any(h in line for h in int_headers):
                current_dest = "int"
                continue
            elif line.startswith("### ") or line.startswith("## "):
                # Other section
                current_dest = "both"
                
            if current_dest == "deriv":
                deriv_parts.append(line)
            elif current_dest == "int":
                int_parts.append(line)
            else:
                # If neutral, we add to both or choose based on heuristic
                deriv_parts.append(line)
                int_parts.append(line)
                
        deriv_str = "\n".join(deriv_parts).strip()
        int_str = "\n".join(int_parts).strip()
        
        if not deriv_str:
            # Fallback split: first half and second half
            split_idx = len(text) // 2
            deriv_str = text[:split_idx]
            int_str = text[split_idx:]
            
        return deriv_str, int_str

    def on_scroll(self, event: ScrollableContainer.Scroll) -> None:
        """Synchronizes vertical scrolling between the two side-by-side panes."""
        left_pane = self.query_one("#left-pane", ScrollableContainer)
        right_pane = self.query_one("#right-pane", ScrollableContainer)
        
        # Determine which container triggered scroll
        if event.container.id == "left-pane":
            # Sync right pane to match left pane's y offset
            right_pane.scroll_y = left_pane.scroll_y
        elif event.container.id == "right-pane":
            # Sync left pane to match right pane's y offset
            left_pane.scroll_y = right_pane.scroll_y
