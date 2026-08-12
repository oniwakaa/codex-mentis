import sqlite3
from typing import Dict, List, Any, Optional
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widget import Widget
from textual.widgets import Label, Select, Input, Button, DataTable, Static

from codex_mentis.core.config import CONFIG_DIR
from codex_mentis.memory.store import MemoryStore

class MemoryViewer(Widget):
    """
    An interactive memory viewer widget for exploring, searching, 
    and auditing L1/L2/L3 memory layers and the knowledge base.
    """
    
    DEFAULT_CSS = """
    MemoryViewer {
        width: 100%;
        height: 100%;
        layout: vertical;
        border: solid $accent;
    }
    
    #viewer-title {
        height: 3;
        background: $boost;
        content-align: center center;
        text-style: bold;
        border-bottom: solid $accent;
    }
    
    #search-bar {
        height: 3;
        layout: horizontal;
        background: $panel;
        align: left middle;
        padding-left: 2;
    }
    
    #search-bar Input {
        width: 40;
        margin-right: 2;
    }
    
    #search-bar Select {
        width: 20;
        margin-right: 2;
    }
    
    #search-bar Button {
        margin-right: 1;
    }
    
    #viewer-split {
        width: 100%;
        height: 1fr;
        layout: vertical;
    }
    
    DataTable {
        height: 1fr;
        background: $background;
        border-bottom: solid $accent;
    }
    
    #entry-detail {
        height: 8;
        background: $panel;
        padding: 1 2;
        color: $text;
        scrollbar-gutter: stable;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = MemoryStore(db_path=str(CONFIG_DIR / "memory.db"))
        self.active_layer = "ALL"
        self.search_query = ""

    def compose(self) -> ComposeResult:
        yield Label("COGNITIVE MEMORY LAYERS AUDITOR", id="viewer-title")
        
        layer_options = [
            ("All Layers", "ALL"),
            ("L1: Episodic Conversation", "L1"),
            ("L2: Summarized Sessions", "L2"),
            ("L3: Synthesized Concepts", "L3"),
        ]
        
        yield Horizontal(
            Input(placeholder="Search memory text...", id="memory-search-input"),
            Select(layer_options, value=self.active_layer, id="layer-select"),
            Button("Search", variant="primary", id="search-btn"),
            Button("Clear Layer", variant="error", id="clear-btn"),
            id="search-bar"
        )
        
        yield Container(
            DataTable(id="memory-table"),
            ScrollableContainer(Static("Select a memory entry to view complete text and metadata.", id="detail-text"), id="entry-detail"),
            id="viewer-split"
        )

    def on_mount(self) -> None:
        table = self.query_one("#memory-table", DataTable)
        table.add_columns("ID", "Layer", "Topic", "Timestamp", "Snippet")
        table.cursor_type = "row"
        self.refresh_memories()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search-btn":
            self.search_query = self.query_one("#memory-search-input", Input).value.strip()
            self.refresh_memories()
        elif event.button.id == "clear-btn":
            self.clear_active_layer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "memory-search-input":
            self.search_query = event.value.strip()
            self.refresh_memories()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "layer-select" and event.value is not None:
            self.active_layer = str(event.value)
            self.refresh_memories()

    def clear_active_layer(self) -> None:
        """Clear database entries in the selected layer."""
        if self.active_layer == "ALL":
            # Clear all layers
            conn = sqlite3.connect(self.store.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_entries")
            conn.commit()
            conn.close()
        else:
            # Clear specific layer
            conn = sqlite3.connect(self.store.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_entries WHERE layer = ?", (self.active_layer,))
            conn.commit()
            conn.close()
            
        self.query_one("#detail-text", Static).update(f"Cleared memory database layer: {self.active_layer}")
        self.refresh_memories()

    def refresh_memories(self) -> None:
        """Fetch memories matching layer/search filters and display them in the data table."""
        table = self.query_one("#memory-table", DataTable)
        table.clear()
        
        filter_layer = None if self.active_layer == "ALL" else self.active_layer
        
        # Check if we should do keyword search or standard listing
        if self.search_query:
            try:
                results = self.store.retrieve(self.search_query, layer=filter_layer, top_k=50)
                # Convert results to standard formats
                entries = []
                for r in results:
                    entries.append({
                        "id": r["id"],
                        "layer": r["layer"],
                        "topic": r["topic"],
                        "timestamp": r["timestamp"],
                        "content": r["content"],
                        "metadata": r.get("metadata", {})
                    })
            except Exception:
                entries = []
        else:
            try:
                mem_entries = self.store.list_memories(layer=filter_layer)
                # Sort by timestamp descending
                mem_entries.sort(key=lambda x: x.timestamp, reverse=True)
                entries = []
                for e in mem_entries:
                    entries.append({
                        "id": e.id,
                        "layer": e.layer,
                        "topic": e.topic,
                        "timestamp": e.timestamp.strftime("%Y-%m-%d %H:%M:%S") if e.timestamp else "N/A",
                        "content": e.content,
                        "metadata": e.metadata
                    })
            except Exception:
                entries = []

        # Keep a mapping of row keys to full entry details for click retrieval
        self.row_data_map = {}
        
        for entry in entries:
            eid = entry["id"]
            layer = entry["layer"]
            topic = entry["topic"]
            ts = entry["timestamp"]
            content = entry["content"]
            
            snippet = content.replace("\n", " ")[:60] + ("..." if len(content) > 60 else "")
            
            row_key = table.add_row(
                str(eid),
                layer,
                topic,
                ts,
                snippet
            )
            self.row_data_map[row_key] = entry

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Triggered when a user clicks on a table row, displaying full entry details."""
        detail = self.query_one("#detail-text", Static)
        row_key = event.row_key
        entry = self.row_data_map.get(row_key)
        
        if entry:
            metadata_str = ""
            if entry.get("metadata"):
                import json
                metadata_str = f"\n\n[bold magenta]Metadata:[/bold magenta]\n{json.dumps(entry['metadata'], indent=2)}"
                
            detail.update(
                f"[bold cyan]ID:[/bold cyan] {entry['id']} | "
                f"[bold cyan]Layer:[/bold cyan] {entry['layer']} | "
                f"[bold cyan]Topic:[/bold cyan] {entry['topic']} | "
                f"[bold cyan]Timestamp:[/bold cyan] {entry['timestamp']}\n\n"
                f"[bold white]Content:[/bold white]\n{entry['content']}"
                f"{metadata_str}"
            )
