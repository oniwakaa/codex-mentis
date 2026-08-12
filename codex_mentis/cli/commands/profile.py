"""Profile commands — view and manage your learning profile."""
import typer

app = typer.Typer(help="User profile and knowledge map")


@app.callback(invoke_without_command=True)
def profile_main(ctx: typer.Context):
    """Show your learning profile."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from codex_mentis.cli.commands.onboard import load_profile, has_profile
    from codex_mentis.memory.user_graph import UserGraph

    console = Console()

    if ctx.invoked_subcommand is not None:
        return

    profile = load_profile()
    if not profile:
        console.print("[yellow]No profile found. Run `codex-mentis onboard` first.[/yellow]")
        return

    # Profile overview
    console.print(Panel(
        f"[bold]Name:[/bold] {profile.get('name', 'Scholar')}\n"
        f"[bold]Interests:[/bold] {', '.join(profile.get('interests', []))}\n"
        f"[bold]Onboarded:[/bold] {profile.get('onboarding_date', 'Unknown')[:10]}",
        title="👤 Profile",
        border_style="blue",
    ))

    # Levels
    levels = profile.get("levels", {})
    if levels:
        table = Table(title="📊 Skill Levels", show_header=True)
        table.add_column("Subject", style="bold")
        table.add_column("Level")
        table.add_column("Score")
        
        for subj, level in levels.items():
            scores = profile.get("diagnostic_scores", {}).get(subj, {})
            pct = scores.get("percentage", 0)
            color = "green" if level == "advanced" else "yellow" if level == "intermediate" else "blue"
            table.add_row(subj.title(), f"[{color}]{level.title()}[/{color}]", f"{pct:.0%}")
        
        console.print(table)

    # Knowledge stats from user graph
    try:
        ug = UserGraph()
        stats = ug.get_user_stats(profile.get("name", "default"))
        if stats["topics_studied"] > 0:
            console.print(Panel(
                f"Topics studied: {stats['topics_studied']}\n"
                f"Concepts mastered: {stats['concepts_mastered']}\n"
                f"Concepts struggling: {stats['concepts_struggling']}\n"
                f"Total study time: {stats['total_hours']}h",
                title="📈 Progress",
                border_style="green",
            ))
    except Exception:
        pass


@app.command("knowledge-map")
def knowledge_map():
    """Visualize your knowledge graph."""
    from rich.console import Console
    from codex_mentis.cli.commands.onboard import load_profile
    from codex_mentis.memory.user_graph import UserGraph

    console = Console()
    profile = load_profile()
    if not profile:
        console.print("[yellow]No profile found. Run `codex-mentis onboard` first.[/yellow]")
        return

    ug = UserGraph()
    viz = ug.visualize_graph(profile.get("name", "default"))
    console.print(viz)


@app.command("gaps")
def knowledge_gaps():
    """Show knowledge gaps — prerequisites you haven't learned yet."""
    from rich.console import Console
    from rich.panel import Panel
    from codex_mentis.cli.commands.onboard import load_profile
    from codex_mentis.memory.user_graph import UserGraph

    console = Console()
    profile = load_profile()
    if not profile:
        console.print("[yellow]No profile found. Run `codex-mentis onboard` first.[/yellow]")
        return

    ug = UserGraph()
    gaps = ug.get_knowledge_gaps(profile.get("name", "default"))
    
    if not gaps:
        console.print("[green]No knowledge gaps found! You're building a solid foundation.[/green]")
        return

    console.print(Panel(
        "\n".join(f"  • {g['concept']} (needed for: {g['needed_for']})" for g in gaps[:10]),
        title="🔍 Knowledge Gaps",
        border_style="yellow",
    ))


@app.command("recommend")
def recommend():
    """Get recommendations for what to study next."""
    from rich.console import Console
    from rich.panel import Panel
    from codex_mentis.cli.commands.onboard import load_profile
    from codex_mentis.memory.user_graph import UserGraph

    console = Console()
    profile = load_profile()
    if not profile:
        console.print("[yellow]No profile found. Run `codex-mentis onboard` first.[/yellow]")
        return

    ug = UserGraph()
    recs = ug.recommend_next(profile.get("name", "default"))
    
    if not recs:
        console.print("[green]No recommendations yet. Start studying to build your profile![/green]")
        return

    console.print(Panel(
        "\n".join(f"  • {r['topic']} — {r['reason']}" for r in recs[:10]),
        title="📚 Recommended Next Topics",
        border_style="cyan",
    ))
