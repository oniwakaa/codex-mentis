from typing import Dict, List, Any, Optional
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Tree, Label, Static
from textual.widget import Widget
from rich.text import Text

class ProofTreeWidget(Widget):
    """
    An interactive proof tree widget showing logical deduction steps as a collapsible tree.
    """
    
    DEFAULT_CSS = """
    ProofTreeWidget {
        width: 100%;
        height: 100%;
        layout: vertical;
        border: solid $accent;
    }
    
    #tree-title {
        height: 3;
        background: $boost;
        content-align: center center;
        text-style: bold;
        border-bottom: solid $accent;
    }
    
    #detail-panel {
        height: 4;
        background: $panel;
        padding: 1 2;
        border-top: solid $accent;
        color: $text;
    }
    
    Tree {
        height: 1fr;
        background: $background;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_label = "Logical Deduction Tree"
        self.proof_data: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("PROOF AUDIT & DEDUCTION TREE", id="tree-title")
        tree = Tree(self.root_label, id="proof-tree")
        tree.root.expand()
        yield tree
        yield Static("Click on any proof node to view derivation details.", id="detail-panel")

    def set_proof_steps(self, steps: List[str], title: str = "Proof Derivation") -> None:
        """Populate the proof tree from a flat list of step strings."""
        tree = self.query_one("#proof-tree", Tree)
        tree.clear()
        
        self.root_label = title
        tree.root.label = Text(title, style="bold magenta")
        
        # Parse steps and build tree
        # If steps look like "Step 1: ...", "Step 1.1: ...", we can construct hierarchy
        current_nodes = {0: tree.root}
        
        for step in steps:
            # Parse step number if possible, e.g. "Step 1.2:"
            import re
            match = re.match(r"(?:Step\s+)?([0-9\.]+)(?:\s*:)?\s*(.*)", step, re.IGNORECASE)
            if match:
                num_str, content = match.groups()
                parts = [int(p) for p in num_str.split(".") if p.isdigit()]
                level = len(parts)
                
                # Find parent node (level - 1)
                parent_node = current_nodes.get(level - 1, tree.root)
                
                # Add node
                node_text = Text.assemble(
                    (f"Step {num_str}: ", "bold yellow"),
                    (content[:60] + ("..." if len(content) > 60 else ""), "white")
                )
                node = parent_node.add(node_text, expand=True)
                node.data = {"content": content, "step": num_str}
                current_nodes[level] = node
            else:
                # Fallback flat step addition
                node_text = Text(step[:70] + ("..." if len(step) > 70 else ""), style="cyan")
                node = tree.root.add(node_text, expand=True)
                node.data = {"content": step, "step": ""}

        tree.root.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Triggered when a user clicks on a proof tree node."""
        detail = self.query_one("#detail-panel", Static)
        node = event.node
        if node.data:
            step_num = node.data.get("step", "")
            content = node.data.get("content", "")
            header = f"[bold yellow]Step {step_num}:[/bold yellow] " if step_num else ""
            detail.update(f"{header}{content}")
        else:
            detail.update("[bold magenta]Root Node:[/bold magenta] Deductive target verified.")
