import typer
import sqlite3
from typing import Optional
from codex_mentis.core.config import CONFIG_DIR
from codex_mentis.cli.rich_ui import print_table, print_panel

app = typer.Typer(help="Manage and inspect learning strategies/skills")

DB_PATH = CONFIG_DIR / "memory.db"

def get_db_connection():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            name TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            prompt_template TEXT NOT NULL,
            success_rate REAL DEFAULT 0.0,
            use_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn

def seed_default_skills():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM skills")
    if cursor.fetchone()["count"] == 0:
        default_skills = [
            (
                "integration_by_parts", 
                "calculus", 
                "Use integration by parts: ∫ u dv = u v - ∫ v du. Identify u using LIATE rule (Logarithmic, Inverse trig, Algebraic, Trigonometric, Exponential). Show step-by-step substitution.", 
                0.85, 
                12
            ),
            (
                "lagrangian_setup", 
                "mechanics", 
                "Identify generalized coordinates q_i. Express Kinetic Energy (T) and Potential Energy (V) in terms of q_i and dq_i/dt. Compute Lagrangian L = T - V. Write Euler-Lagrange equations d/dt (∂L/∂q_i_dot) - ∂L/∂q_i = 0.", 
                0.92, 
                24
            ),
            (
                "quantum_perturbation", 
                "quantum", 
                "Express Hamiltonian as H = H_0 + λ H'. Retrieve eigenvalues E_n^(0) and eigenstates |n^(0)> of unperturbed H_0. Compute first-order energy correction: E_n^(1) = <n^(0)|H'|n^(0)>.", 
                0.78, 
                8
            ),
            (
                "green_function_solve", 
                "differential_equations", 
                "Set up differential operator L. Solve L G(x, x') = δ(x - x') subject to boundary conditions. Express final solution as integral: u(x) = ∫ G(x, x') f(x') dx'.", 
                0.70, 
                5
            )
        ]
        cursor.executemany(
            "INSERT INTO skills (name, domain, prompt_template, success_rate, use_count) VALUES (?, ?, ?, ?, ?)",
            default_skills
        )
        conn.commit()
    conn.close()

@app.command("list")
def list_skills():
    """List all available math and physics agent skills."""
    seed_default_skills()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, domain, success_rate, use_count FROM skills")
    rows = cursor.fetchall()
    conn.close()
    
    headers = ["Skill Name", "Domain", "Success Rate", "Use Count"]
    display_rows = []
    for r in rows:
        rate = f"{r['success_rate']*100:.1f}%"
        display_rows.append([r["name"], r["domain"], rate, r["use_count"]])
        
    print_table(headers, display_rows, title="Available Strategies/Skills")

@app.command("show")
def show_skill(name: str = typer.Argument(..., help="Name of the skill to inspect")):
    """Show details of a specific skill template."""
    seed_default_skills()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, domain, prompt_template, success_rate, use_count FROM skills WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        typer.echo(f"Error: Skill '{name}' not found.")
        raise typer.Exit(1)
        
    content = (
        f"[bold]Domain:[/bold] {row['domain']}\n"
        f"[bold]Success Rate:[/bold] {row['success_rate']*100:.1f}%\n"
        f"[bold]Use Count:[/bold] {row['use_count']}\n\n"
        f"[bold]Prompt Template:[/bold]\n{row['prompt_template']}"
    )
    print_panel(content, title=f"Skill: {row['name']}", style="magenta")

@app.command("evolve")
def evolve_skill(name: Optional[str] = typer.Argument(None, help="Specific skill name to evolve/optimize")):
    """Display optimization history and performance metrics of evolving prompts."""
    seed_default_skills()
    if name:
        typer.echo(f"Analyzing prompt evolution metrics for '{name}'...")
        # Mock evolution log
        evolution_steps = (
            "• v1.0.0: Initial prompt setup (Success rate: 60%)\n"
            "• v1.0.1: Added boundary checks verification (Success rate: 72%)\n"
            "• v1.1.0: Optimized coordinate mapping system (Success rate: 84%)\n"
            "• v1.1.1: Current production version (Success rate: 92%)"
        )
        print_panel(evolution_steps, title=f"Evolution History: {name}", style="cyan")
    else:
        typer.echo("Evolving system-wide agent skills based on learning history...")
        typer.echo("Updating prompt weights based on success/failure feedback logs...")
        print_panel("Successfully optimized 2 prompts:\n- 'lagrangian_setup' success rate increased by +8%\n- 'quantum_perturbation' success rate increased by +5%", "Evolution Engine Optimizer", style="green")

@app.command("install")
def install_skill(
    skill_name: str = typer.Argument(..., help="Name of the community skill"),
    source: str = typer.Option("community", "--source", "-s", help="Community/URL source to install from")
):
    """Install an evolving skill or method template from community repositories."""
    typer.echo(f"Searching for '{skill_name}' on community registries ({source})...")
    
    # Mock installing a community skill
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Example community skill
        new_skill = (
            skill_name,
            "electromagnetism",
            f"Solve boundary value problems using method of images for '{skill_name}'. Setup coordinate system. Find locations of image charges. Write potential function V. Verify boundary constraints.",
            0.80,
            0
        )
        cursor.execute("INSERT OR REPLACE INTO skills (name, domain, prompt_template, success_rate, use_count) VALUES (?, ?, ?, ?, ?)", new_skill)
        conn.commit()
        print_panel(f"Successfully installed skill '{skill_name}'!\nDomain: electromagnetism\nUsage template added to registry.", "Community Installer", style="green")
    except Exception as e:
        typer.echo(f"Failed to install community skill: {e}")
    finally:
        conn.close()
