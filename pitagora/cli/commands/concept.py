import typer
import yaml
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional
from pitagora.core.config import CONFIG_DIR
from pitagora.cli.rich_ui import print_concept_map, print_table, print_panel
from pitagora.core.constants import DEFAULT_CONCEPTS

app = typer.Typer(help="Inspect and track math/physics concept mastery")

DB_PATH = CONFIG_DIR / "memory.db"

def get_db_connection():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Ensure tables exist
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS concept_mastery (
            concept_id TEXT PRIMARY KEY,
            mastery_score REAL DEFAULT 0.0,
            last_reviewed TEXT
        )
    """)
    conn.commit()
    return conn

def load_all_concepts() -> Dict[str, List[Dict[str, Any]]]:
    path = Path(__file__).parent.parent.parent / "data" / "concepts.yaml"
    if path.exists():
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
            
    # Fallback to basic structure from constants
    fallback = {}
    for domain, names in DEFAULT_CONCEPTS.items():
        fallback[domain] = []
        for idx, name in enumerate(names):
            cid = f"{domain}_{name.lower().replace(' ', '_')}"
            prereq = []
            if idx > 0:
                # Chain them simply for mock purposes
                prev_name = names[idx - 1]
                prereq.append(f"{domain}_{prev_name.lower().replace(' ', '_')}")
            fallback[domain].append({
                "id": cid,
                "name": name,
                "prerequisites": prereq
            })
    return fallback

def get_mastery_dict() -> Dict[str, float]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT concept_id, mastery_score FROM concept_mastery")
    rows = cursor.fetchall()
    conn.close()
    return {row["concept_id"]: row["mastery_score"] for row in rows}

@app.command("map")
def show_map(
    concept_id: Optional[str] = typer.Argument(None, help="Specific concept ID to draw map for"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Domain to filter by")
):
    """Display the concept dependency graph/map."""
    concepts_data = load_all_concepts()
    
    # Flatten concepts list
    flat_concepts = {}
    concept_names = {}
    prereq_map = {}
    
    for dom, items in concepts_data.items():
        if domain and dom != domain:
            continue
        for item in items:
            cid = item["id"]
            flat_concepts[cid] = item
            concept_names[cid] = item["name"]
            prereq_map[cid] = item.get("prerequisites", [])
            
    if concept_id:
        if concept_id not in flat_concepts:
            typer.echo(f"Error: Concept '{concept_id}' not found.")
            raise typer.Exit(1)
        typer.echo(f"Showing prerequisites map for {concept_names[concept_id]}:")
        print_concept_map(concept_id, prereq_map, concept_names)
    else:
        # Show all concepts by domain
        for dom, items in concepts_data.items():
            if domain and dom != domain:
                continue
            typer.echo(f"\n[Domain: {dom.upper()}]")
            for item in items:
                prereqs_str = ", ".join(item.get("prerequisites", []))
                prereqs_display = f" (prereqs: {prereqs_str})" if prereqs_str else ""
                typer.echo(f"  • {item['name']} ({item['id']}){prereqs_display}")

@app.command("status")
def show_status(domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter by domain")):
    """Show mastery scores for concepts."""
    concepts_data = load_all_concepts()
    mastery = get_mastery_dict()
    
    headers = ["Domain", "Concept Name", "Concept ID", "Mastery Score"]
    rows = []
    
    for dom, items in concepts_data.items():
        if domain and dom != domain:
            continue
        for item in items:
            cid = item["id"]
            score = mastery.get(cid, 0.0)
            score_bar = f"{score * 100:.1f}%"
            # Visual indicator
            if score >= 0.8:
                status_str = f"[green]{score_bar}[/green]"
            elif score >= 0.4:
                status_str = f"[yellow]{score_bar}[/yellow]"
            else:
                status_str = f"[red]{score_bar}[/red]"
            rows.append([dom, item["name"], cid, status_str])
            
    print_table(headers, rows, title="Concept Mastery Overview")

@app.command("next")
def suggest_next(domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter by domain")):
    """Suggest the next topic to study based on prerequisites and current mastery."""
    concepts_data = load_all_concepts()
    mastery = get_mastery_dict()
    
    suggested = []
    
    # We find concepts with < 80% mastery whose prerequisites are all >= 80% mastered (or have no prerequisites)
    for dom, items in concepts_data.items():
        if domain and dom != domain:
            continue
        for item in items:
            cid = item["id"]
            score = mastery.get(cid, 0.0)
            if score >= 0.8:
                continue # Already mastered
                
            prereqs = item.get("prerequisites", [])
            prereqs_satisfied = True
            for pr in prereqs:
                if mastery.get(pr, 0.0) < 0.8:
                    prereqs_satisfied = False
                    break
                    
            if prereqs_satisfied:
                suggested.append((dom, item["name"], cid, score))
                
    if not suggested:
        print_panel("Congratulations! You have mastered all topics or no recommendations fit your current state.", "Next Study Recommendations", style="green")
    else:
        headers = ["Domain", "Concept Name", "Concept ID", "Current Mastery"]
        rows = [[item[0], item[1], item[2], f"{item[3] * 100:.1f}%"] for item in suggested[:5]]
        print_table(headers, rows, title="Recommended Next Topics to Study")

@app.command("review")
def show_review_queue():
    """Show the spaced repetition review queue."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Mock queue logic: anything with last_reviewed or a low mastery score < 0.5 needs review
    cursor.execute("SELECT concept_id, mastery_score, last_reviewed FROM concept_mastery WHERE mastery_score < 0.8")
    rows = cursor.fetchall()
    conn.close()
    
    concepts_data = load_all_concepts()
    # Map ID to metadata
    id_map = {}
    for dom, items in concepts_data.items():
        for item in items:
            id_map[item["id"]] = item
            
    if not rows:
        # Grab a few default ones with 0 mastery if the database is clean
        count = 0
        headers = ["Concept Name", "Concept ID", "Reason"]
        display_rows = []
        for dom, items in concepts_data.items():
            for item in items[:2]:
                display_rows.append([item["name"], item["id"], "Initial Study Needed"])
                count += 1
                if count >= 4:
                    break
            if count >= 4:
                break
        print_table(headers, display_rows, title="Spaced Repetition Queue (Initial Review)")
    else:
        headers = ["Concept Name", "Concept ID", "Current Mastery", "Last Reviewed"]
        display_rows = []
        for row in rows:
            cid = row["concept_id"]
            if cid in id_map:
                name = id_map[cid]["name"]
                display_rows.append([name, cid, f"{row['mastery_score']*100:.1f}%", row["last_reviewed"] or "Never"])
        print_table(headers, display_rows, title="Due for Review (Spaced Repetition)")
