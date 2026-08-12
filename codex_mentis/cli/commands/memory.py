import typer
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from codex_mentis.core.config import CONFIG_DIR
from codex_mentis.cli.rich_ui import print_table, print_panel, print_markdown

app = typer.Typer(help="Manage and query Codex Mentis memory layers")

DB_PATH = CONFIG_DIR / "memory.db"

def get_db_connection():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            layer TEXT NOT NULL,
            content TEXT NOT NULL,
            topic TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            embedding TEXT
        )
    """)
    conn.commit()
    return conn

@app.command("show")
def show_memory(layer: Optional[str] = typer.Option(None, "--layer", "-l", help="Specific layer to show (L1/L2/L3)")):
    """Display entries in L1 (Session), L2 (Topic), and L3 (Synthesis) memory."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if layer:
        cursor.execute("SELECT id, layer, content, topic, timestamp FROM memory_entries WHERE layer = ? ORDER BY timestamp DESC", (layer.upper(),))
    else:
        cursor.execute("SELECT id, layer, content, topic, timestamp FROM memory_entries ORDER BY layer, timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        typer.echo("No memory entries found. Start studying or exploring to populate memory!")
        return
        
    headers = ["ID", "Layer", "Topic", "Timestamp", "Content Summary"]
    display_rows = []
    for r in rows:
        content = r["content"]
        summary = content if len(content) < 60 else content[:57] + "..."
        display_rows.append([r["id"], r["layer"], r["topic"], r["timestamp"], summary])
        
    print_table(headers, display_rows, title="Memory Entries")

@app.command("search")
def search_memory(query: str = typer.Argument(..., help="Query to search memory for")):
    """Perform a search on memory database. Uses semantic embedding search if model is available, falling back to substring matching."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, layer, content, topic, timestamp, embedding FROM memory_entries")
    rows = cursor.fetchall()
    
    if not rows:
        typer.echo("No memory entries to search.")
        conn.close()
        return
        
    # Attempt semantic embedding search if sentence-transformers is installed
    semantic_success = False
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        
        # Lazy load model
        model = SentenceTransformer("all-MiniLM-L6-v2")
        query_emb = model.encode(query)
        
        scores = []
        for r in rows:
            emb_str = r["embedding"]
            if emb_str:
                emb = np.array(json.loads(emb_str))
                # Cosine similarity
                sim = np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb))
                scores.append((sim, r))
            else:
                scores.append((0.0, r))
                
        # Sort by similarity score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        results = [s[1] for s in scores if s[0] > 0.3][:5]
        semantic_success = len(results) > 0
    except Exception:
        # Fallback to local SQL keyword search
        pass
        
    if not semantic_success:
        # Fallback keyword matching
        cursor.execute("SELECT id, layer, content, topic, timestamp FROM memory_entries WHERE content LIKE ? OR topic LIKE ? ORDER BY timestamp DESC", (f"%{query}%", f"%{query}%"))
        results = cursor.fetchall()
        
    conn.close()
    
    if not results:
        typer.echo("No matching memory entries found.")
        return
        
    typer.echo(f"Search Results for: '{query}'")
    for idx, r in enumerate(results, 1):
        content_preview = r["content"]
        title = f"{idx}. [{r['layer']}] {r['topic']} - {r['timestamp']}"
        print_panel(content_preview, title, style="cyan")

@app.command("clear")
def clear_memory(
    layer: str = typer.Option("L1", "--layer", "-l", help="Which memory layer to clear (L1/L2/L3 or ALL)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force clear without prompt")
):
    """Clear memory entries."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to clear '{layer}' memory?")
        if not confirm:
            typer.echo("Operation cancelled.")
            return
            
    conn = get_db_connection()
    cursor = conn.cursor()
    if layer.upper() == "ALL":
        cursor.execute("DELETE FROM memory_entries")
    else:
        cursor.execute("DELETE FROM memory_entries WHERE layer = ?", (layer.upper(),))
    conn.commit()
    conn.close()
    typer.echo(f"Successfully cleared '{layer}' memory.")

@app.command("export")
def export_memory(output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Target markdown file path")):
    """Export memory entries to a formatted markdown document."""
    if not output_file:
        output_file = CONFIG_DIR / "memory_export.md"
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT layer, content, topic, timestamp FROM memory_entries ORDER BY layer, timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        typer.echo("No memory entries to export.")
        return
        
    md_content = "# Codex Mentis - Exported Memory Vault\n\n"
    current_layer = None
    
    for r in rows:
        layer = r["layer"]
        if layer != current_layer:
            current_layer = layer
            md_content += f"## {current_layer} Memory\n\n"
            
        md_content += f"### Topic: {r['topic']}\n"
        md_content += f"*Timestamp: {r['timestamp']}*\n\n"
        md_content += f"{r['content']}\n\n"
        md_content += "---\n\n"
        
    try:
        with open(output_file, "w") as f:
            f.write(md_content)
        typer.echo(f"Memory successfully exported to {output_file}")
    except Exception as e:
        typer.echo(f"Failed to write memory export: {e}")
