import re
from typing import Tuple
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Static
from codex_mentis.cli.widgets.equation_display import latex_to_unicode

def color_code_derivation(text: str) -> str:
    """Color-codes technical derivations: cyan for equations, yellow for definitions, green for proofs."""
    # Convert any LaTeX to Unicode math
    unicode_text = latex_to_unicode(text)
    
    lines = unicode_text.split("\n")
    styled_lines = []
    
    # Multi-line state trackers
    in_box = False
    
    for line in lines:
        lower = line.lower()
        
        # Detect mathematical unicode box boundaries
        if any(char in line for char in ["┌", "├", "└", "─"]):
            in_box = True
            styled_lines.append(f"[cyan]{line}[/cyan]")
            if "┘" in line or "└" in line:
                in_box = False
            continue
        elif in_box or "│" in line:
            styled_lines.append(f"[cyan]{line}[/cyan]")
            if "┘" in line or "└" in line:
                in_box = False
            continue
            
        if "definition" in lower or "define" in lower or "def:" in lower:
            styled_lines.append(f"[yellow]{line}[/yellow]")
        elif "proof" in lower or "q.e.d" in lower or "qed" in lower or "step" in lower or "derive" in lower:
            styled_lines.append(f"[green]{line}[/green]")
        elif any(char in line for char in ["θ", "π", "∫", "∑", "√", "λ", "μ", "α", "β", "γ", "δ", "ε", "ħ", "∂", "≈", "≠", "≤", "≥", "∈"]):
            styled_lines.append(f"[cyan]{line}[/cyan]")
        else:
            # Try highlighting general inline math variables or equations
            if "$" in line or "=" in line:
                styled_lines.append(f"[cyan]{line}[/cyan]")
            else:
                styled_lines.append(line)
                
    return "\n".join(styled_lines)

def color_code_intuition(text: str) -> str:
    """Color-codes intuition: yellow for definitions, green for core concepts, magenta for analogies."""
    lines = text.split("\n")
    styled_lines = []
    
    for line in lines:
        lower = line.lower()
        if "definition" in lower or "define" in lower:
            styled_lines.append(f"[yellow]{line}[/yellow]")
        elif "analogy" in lower or "analogous" in lower or "like a" in lower or "think of" in lower or "imagine" in lower:
            styled_lines.append(f"[magenta]{line}[/magenta]")
        elif "intuition" in lower or "concept" in lower or "explain" in lower:
            styled_lines.append(f"[green]{line}[/green]")
        else:
            styled_lines.append(line)
            
    return "\n".join(styled_lines)

class SyncedScrollContainer(ScrollableContainer):
    """A ScrollableContainer that synchronizes its scroll position with another container."""
    other_container = None
    _scrolling = False

    def watch_scroll_x(self, value: float) -> None:
        if self.other_container and not self._scrolling:
            self.other_container._scrolling = True
            self.other_container.scroll_to(x=value, animate=False)
            self.other_container._scrolling = False

    def watch_scroll_y(self, value: float) -> None:
        if self.other_container and not self._scrolling:
            self.other_container._scrolling = True
            self.other_container.scroll_to(y=value, animate=False)
            self.other_container._scrolling = False

class SplitReasoning(Vertical):
    """Side-by-side panel showcasing mathematical derivation vs plain-English intuition."""
    
    DEFAULT_CSS = """
    SplitReasoning {
        height: 1fr;
        width: 100%;
        border: solid $accent;
    }
    .column-wrapper {
        width: 50fr;
        height: 1fr;
    }
    .column-wrapper-left {
        border-right: tall $accent;
    }
    .column-title {
        background: $primary;
        color: $text;
        text-align: center;
        text-style: bold;
        height: 1;
        width: 100%;
    }
    .col-content {
        padding: 1 2;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="panels-container"):
            with Vertical(classes="column-wrapper column-wrapper-left") as left_col:
                yield Static("TECHNICAL DERIVATION (FORMAL MATH)", classes="column-title")
                with SyncedScrollContainer(id="derivation_scroll") as derivation_scroll:
                    yield Static(id="derivation_content", classes="col-content")
                    
            with Vertical(classes="column-wrapper") as right_col:
                yield Static("PHYSICAL INTUITION (PLAIN ENGLISH)", classes="column-title")
                with SyncedScrollContainer(id="intuition_scroll") as intuition_scroll:
                    yield Static(id="intuition_content", classes="col-content")

    def on_mount(self) -> None:
        # Link scrollbars
        left = self.query_one("#derivation_scroll", SyncedScrollContainer)
        right = self.query_one("#intuition_scroll", SyncedScrollContainer)
        left.other_container = right
        right.other_container = left

    def update_reasoning(self, derivation: str, intuition: str) -> None:
        """Update both panels with content."""
        derivation_styled = color_code_derivation(derivation)
        intuition_styled = color_code_intuition(intuition)
        
        self.query_one("#derivation_content", Static).update(derivation_styled)
        self.query_one("#intuition_content", Static).update(intuition_styled)

    def parse_and_update(self, merged_text: str) -> None:
        """Parse a combined output string and partition it into the side-by-side columns."""
        # Clean string first
        merged_text = merged_text.strip()
        
        # Split on headers
        tutor_headers = [
            "### Conceptual & Intuitive Breakdown",
            "### Physical Intuition",
            "### Intuitive Breakdown",
            "### 1. Conceptual Breakdown",
            "### Intuition",
            "### Conceptual & Intuitive Breakdown (Tutor)"
        ]
        prover_headers = [
            "### Rigorous Mathematical Derivation",
            "### Technical Derivation",
            "### Mathematical Derivation",
            "### Rigorous Proof",
            "### Proof",
            "### Rigorous Mathematical Derivation (Prover)"
        ]
        
        # Try a regex-based search for headers
        tutor_idx = -1
        prover_idx = -1
        tutor_header_len = 0
        prover_header_len = 0
        
        for h in tutor_headers:
            idx = merged_text.find(h)
            if idx != -1:
                tutor_idx = idx
                tutor_header_len = len(h)
                break
                
        for h in prover_headers:
            idx = merged_text.find(h)
            if idx != -1:
                prover_idx = idx
                prover_header_len = len(h)
                break
                
        if tutor_idx != -1 and prover_idx != -1:
            if tutor_idx < prover_idx:
                intuition = merged_text[tutor_idx + tutor_header_len : prover_idx].strip()
                derivation = merged_text[prover_idx + prover_header_len :].strip()
            else:
                derivation = merged_text[prover_idx + prover_header_len : tutor_idx].strip()
                intuition = merged_text[tutor_idx + tutor_header_len :].strip()
        else:
            # Fallback split: try parsing by sections or just put the whole text in both
            parts = merged_text.split("###", 2)
            if len(parts) >= 3:
                # Guess which is which
                p1_lower = parts[1].lower()
                if "tutor" in p1_lower or "concept" in p1_lower or "intuition" in p1_lower:
                    intuition = parts[1]
                    derivation = parts[2]
                else:
                    derivation = parts[1]
                    intuition = parts[2]
            else:
                # If cannot parse cleanly, display general text
                derivation = merged_text
                intuition = merged_text
                
        self.update_reasoning(derivation, intuition)
