import typer
import sqlite3
from typing import Optional
from codex_mentis.core.config import CONFIG_DIR
from codex_mentis.cli.rich_ui import print_panel, print_table
from codex_mentis.chat import launch_chat as launch_repl

app = typer.Typer(help="Initiate Socratic study mode for a math/physics topic")

DB_PATH = CONFIG_DIR / "memory.db"

def check_prerequisites(topic: str) -> list[str]:
    """Inspect local database/YAML concepts to find prerequisites for the study topic."""
    # Find matching concept
    from codex_mentis.cli.commands.concept import load_all_concepts
    concepts_data = load_all_concepts()
    
    found_prereqs = []
    normalized = topic.lower().strip()
    
    for dom, items in concepts_data.items():
        for item in items:
            if normalized in item["name"].lower() or normalized in item["id"].lower():
                found_prereqs.extend(item.get("prerequisites", []))
                
    return found_prereqs

def search_related_kb(topic: str) -> str:
    """Fetch relevant knowledge chunks from the KB database to bootstrap session context."""
    context_chunks = []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT text FROM kb_chunks 
            WHERE text LIKE ? OR doc_path LIKE ? 
            LIMIT 2
        """, (f"%{topic}%", f"%{topic}%"))
        rows = cursor.fetchall()
        for r in rows:
            context_chunks.append(r["text"])
        conn.close()
    except Exception:
        pass
        
    if context_chunks:
        return "\n\n---\n\n".join(context_chunks)
    return "No exact reference material found in knowledge base."

@app.command()
def study(
    topic: str = typer.Argument(..., help="Specific topic or concept to study"),
    domain: str = typer.Option("physics", "--domain", "-d", help="Domain classification (math/physics)"),
    difficulty: int = typer.Option(2, "--difficulty", "-g", min=1, max=5, help="Difficulty level (1-5)")
):
    """Start Socratic tutoring dialogue on a given concept."""
    typer.echo(f"Initializing Study Mode for topic: '{topic}'...")
    
    # 1. Check prerequisites
    prereqs = check_prerequisites(topic)
    if prereqs:
        typer.echo(f"Prerequisite concepts identified: {', '.join(prereqs)}")
    else:
        typer.echo("No prerequisites found in local registry (or starting from scratch).")
        
    # 2. Query Knowledge Base
    kb_context = search_related_kb(topic)
    
    # 3. Enter REPL
    launch_repl(
        mode="STUDY",
        topic=topic,
        context=kb_context,
        domain=domain,
        difficulty=difficulty
    )
