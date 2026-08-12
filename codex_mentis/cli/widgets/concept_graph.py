import sqlite3
from typing import Dict, List, Any, Optional, Tuple, Set
from pathlib import Path
import yaml

from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widget import Widget
from textual.widgets import Static, Label, Select
from textual.message import Message
from rich.text import Text

from codex_mentis.core.config import CONFIG_DIR
from codex_mentis.cli.commands.concept import load_all_concepts, get_mastery_dict

class ConceptSelected(Message):
    """Event fired when a concept node is clicked."""
    def __init__(self, concept_id: str, concept_name: str) -> None:
        super().__init__()
        self.concept_id = concept_id
        self.concept_name = concept_name

class ConceptNode(Static):
    """Clickable and styled node representing a single concept."""
    def __init__(self, concept_id: str, name: str, score: float, **kwargs):
        super().__init__(**kwargs)
        self.concept_id = concept_id
        self.concept_name = name
        self.score = score
        
        # Color coding classes based on mastery score
        if score >= 0.8:
            self.add_class("mastered")
        elif score >= 0.4:
            self.add_class("learning")
        else:
            self.add_class("unlearned")

    def render(self) -> Text:
        score_pct = f"{self.score * 100:.0f}%"
        return Text.assemble(
            (f"{self.concept_name}\n", "bold"),
            (f"[{score_pct}]", "italic")
        )

    def on_click(self) -> None:
        self.post_message(ConceptSelected(self.concept_id, self.concept_name))

class GraphCanvas(Static):
    """Background canvas that draws connecting lines between nodes using box-drawing characters."""
    def __init__(self, width: int, height: int, connections: List[Tuple[Tuple[int, int], Tuple[int, int]]], **kwargs):
        super().__init__(**kwargs)
        self.canvas_width = max(width, 1)
        self.canvas_height = max(height, 1)
        self.connections = connections

    def render(self) -> Text:
        grid = [[" " for _ in range(self.canvas_width)] for _ in range(self.canvas_height)]
        
        def set_char(x: int, y: int, char: str):
            if 0 <= x < self.canvas_width and 0 <= y < self.canvas_height:
                grid[y][x] = char

        for (x1, y1), (x2, y2) in self.connections:
            if x1 == x2 and y1 == y2:
                continue
            x_mid = (x1 + x2) // 2
            
            # Draw horizontal segment 1
            for x in range(min(x1, x_mid), max(x1, x_mid) + 1):
                set_char(x, y1, "─")
            
            # Draw vertical segment
            for y in range(min(y1, y2), max(y1, y2) + 1):
                set_char(x_mid, y, "│")
            
            # Draw horizontal segment 2
            for x in range(min(x_mid, x2), max(x_mid, x2) + 1):
                set_char(x, y2, "─")
            
            # Draw corners
            if y1 < y2:
                set_char(x_mid, y1, "┐")
                set_char(x_mid, y2, "└")
            elif y1 > y2:
                set_char(x_mid, y1, "┘")
                set_char(x_mid, y2, "┌")

        lines = ["".join(row) for row in grid]
        return Text("\n".join(lines), style="grey37")

class ConceptGraphWidget(Container):
    """The main interactive Concept Graph widget containing nodes and background canvas."""
    
    DEFAULT_CSS = """
    ConceptGraphWidget {
        width: 100%;
        height: 100%;
        layout: vertical;
        border: solid $accent;
    }
    
    #controls {
        height: 3;
        width: 100%;
        background: $panel;
        layout: horizontal;
        align: left middle;
        padding-left: 2;
    }
    
    #controls Label {
        margin-right: 2;
        content-align: center center;
    }
    
    #controls Select {
        width: 30;
    }
    
    #scroll-container {
        width: 100%;
        height: 1fr;
        position: relative;
    }
    
    ConceptNode {
        width: 24;
        height: 3;
        border: tall white;
        text-align: center;
        content-align: center center;
        position: absolute;
    }
    
    ConceptNode.mastered {
        background: darkgreen;
        color: white;
        border: tall green;
    }
    
    ConceptNode.learning {
        background: orange;
        color: black;
        border: tall gold;
    }
    
    ConceptNode.unlearned {
        background: darkred;
        color: white;
        border: tall crimson;
    }
    
    GraphCanvas {
        position: absolute;
        left: 0;
        top: 0;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.concepts_data = load_all_concepts()
        self.mastery = get_mastery_dict()
        self.selected_domain = "calculus"  # Default domain

    def compose(self) -> ComposeResult:
        # Populate select options
        domains = list(self.concepts_data.keys())
        options = [(dom.replace("_", " ").title(), dom) for dom in domains]
        
        yield Container(
            Label("Filter Domain:"),
            Select(options, value=self.selected_domain, id="domain-select"),
            id="controls"
        )
        yield ScrollableContainer(id="scroll-container")

    def on_mount(self) -> None:
        self.rebuild_graph()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "domain-select" and event.value is not None:
            self.selected_domain = str(event.value)
            self.rebuild_graph()

    def rebuild_graph(self) -> None:
        """Computes coordinates, populates nodes, and draws connection lines."""
        scroll_container = self.query_one("#scroll-container", ScrollableContainer)
        # Clear existing children
        for child in list(scroll_container.children):
            child.remove()

        # Get active domain concepts
        concepts = self.concepts_data.get(self.selected_domain, [])
        if not concepts:
            return

        # 1. Compute DAG layers
        concept_ids = {c["id"] for c in concepts}
        adj: Dict[str, List[str]] = {}
        in_degree: Dict[str, int] = {}
        
        for c in concepts:
            cid = c["id"]
            adj[cid] = []
            in_degree[cid] = 0
            
        for c in concepts:
            cid = c["id"]
            # Only consider prerequisites inside this domain/set
            prereqs = [p for p in c.get("prerequisites", []) if p in concept_ids]
            for pr in prereqs:
                adj[pr].append(cid)
                in_degree[cid] += 1

        # Kahn's algorithm or simple layer assignment
        layers: Dict[str, int] = {}
        queue = [cid for cid, deg in in_degree.items() if deg == 0]
        
        for cid in queue:
            layers[cid] = 0
            
        while queue:
            curr = queue.pop(0)
            curr_layer = layers[curr]
            for neighbor in adj[curr]:
                layers[neighbor] = max(layers.get(neighbor, 0), curr_layer + 1)
                # Simple topological expansion
                if neighbor not in queue:
                    queue.append(neighbor)

        # 2. Position nodes
        # col_spacing = 30 characters
        # row_spacing = 5 lines
        col_width = 24
        col_spacing = 32
        row_height = 3
        row_spacing = 5
        
        # Group node IDs by their layers
        layer_groups: Dict[int, List[str]] = {}
        for cid, layer in layers.items():
            layer_groups.setdefault(layer, []).append(cid)
            
        positions: Dict[str, Tuple[int, int]] = {}
        max_x = 0
        max_y = 0
        
        for layer, cids in layer_groups.items():
            cids.sort() # alphabetical ordering within columns for determinism
            for idx, cid in enumerate(cids):
                x = layer * col_spacing + 3
                y = idx * row_spacing + 2
                positions[cid] = (x, y)
                max_x = max(max_x, x + col_width)
                max_y = max(max_y, y + row_height)

        # Create background canvas connections
        connections = []
        for c in concepts:
            cid = c["id"]
            if cid not in positions:
                continue
            cx, cy = positions[cid]
            # Center-right connection point of prerequisite
            p_conn = (cx + col_width, cy + row_height // 2)
            
            prereqs = [p for p in c.get("prerequisites", []) if p in positions]
            for pr in prereqs:
                px, py = positions[pr]
                # Center-right of prerequisite, center-left of dependent
                pr_conn = (px + col_width, py + row_height // 2)
                dep_conn = (cx, cy + row_height // 2)
                connections.append((pr_conn, dep_conn))

        # Mount canvas first (draw background)
        canvas = GraphCanvas(
            width=max_x + 5,
            height=max_y + 3,
            connections=connections,
            id="graph-canvas"
        )
        scroll_container.mount(canvas)

        # Mount node widgets
        for c in concepts:
            cid = c["id"]
            if cid not in positions:
                continue
            x, y = positions[cid]
            score = self.mastery.get(cid, 0.0)
            
            node = ConceptNode(
                concept_id=cid,
                name=c["name"],
                score=score,
                classes="concept-node"
            )
            node.styles.offset = (x, y)
            scroll_container.mount(node)
            
        # Update mastery overview dynamically
        self.mastery = get_mastery_dict()
