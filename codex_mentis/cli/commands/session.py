"""Session management — track study sessions with timers."""
import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Study session management")


def _get_db_path():
    from codex_mentis.core.config import CONFIG_DIR
    return str(CONFIG_DIR / "sessions.db")


def _init_db():
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            duration_minutes REAL DEFAULT 0,
            concepts_covered TEXT DEFAULT '[]',
            notes TEXT DEFAULT ''
        );
    """)
    conn.close()
    return db_path


@app.command("start")
def session_start(
    topic: str = typer.Argument("general", help="Topic for this study session"),
):
    """Start a timed study session."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    db_path = _init_db()
    conn = sqlite3.connect(db_path)
    
    # Check for active session
    active = conn.execute(
        "SELECT id, topic, started_at FROM sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    
    if active:
        console.print(f"[yellow]Session already active: '{active[1]}' (started {active[2][:16]})[/yellow]")
        console.print("[dim]Run `codex-mentis session end` first.[/dim]")
        conn.close()
        return

    now = datetime.now().isoformat()
    conn.execute("INSERT INTO sessions (topic, started_at) VALUES (?, ?)", (topic, now))
    conn.commit()
    conn.close()

    console.print(Panel(
        f"[green]Study session started![/green]\n\n"
        f"Topic: [bold]{topic}[/bold]\n"
        f"Started: [cyan]{now[:16]}[/cyan]\n\n"
        f"[dim]When done, run: codex-mentis session end[/dim]",
        title="⏱️ Session",
        border_style="green",
    ))


@app.command("end")
def session_end(
    notes: str = typer.Option("", "--notes", "-n", help="Session notes"),
):
    """End the current study session and show summary."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    
    active = conn.execute(
        "SELECT id, topic, started_at FROM sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    
    if not active:
        console.print("[yellow]No active session. Start one with: codex-mentis session start <topic>[/yellow]")
        conn.close()
        return

    session_id, topic, started_at = active
    now = datetime.now()
    start = datetime.fromisoformat(started_at)
    duration = (now - start).total_seconds() / 60.0

    conn.execute(
        "UPDATE sessions SET ended_at = ?, duration_minutes = ?, notes = ? WHERE id = ?",
        (now.isoformat(), round(duration, 1), notes, session_id)
    )
    conn.commit()
    conn.close()

    # Record in user graph
    try:
        from codex_mentis.memory.user_graph import UserGraph
        from codex_mentis.cli.commands.onboard import load_profile
        profile = load_profile()
        if profile:
            ug = UserGraph()
            ug.record_study(profile.get("name", "default"), topic, duration)
    except Exception:
        pass

    console.print(Panel(
        f"[green]Session complete![/green]\n\n"
        f"Topic: [bold]{topic}[/bold]\n"
        f"Duration: [cyan]{duration:.0f} minutes[/cyan]\n"
        f"{'Notes: ' + notes if notes else ''}",
        title="📊 Session Summary",
        border_style="green",
    ))


@app.command("log")
def session_log(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of sessions to show"),
):
    """Show study session history."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    db_path = _init_db()
    conn = sqlite3.connect(db_path)
    
    rows = conn.execute(
        "SELECT topic, started_at, duration_minutes, notes FROM sessions WHERE ended_at IS NOT NULL ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()

    if not rows:
        console.print("[yellow]No completed sessions yet.[/yellow]")
        return

    table = Table(title="📚 Study Sessions", show_header=True)
    table.add_column("Date", style="cyan")
    table.add_column("Topic", style="bold")
    table.add_column("Duration", justify="right")
    table.add_column("Notes")

    for topic, started, duration, notes in rows:
        date_str = started[:10] if started else "?"
        dur_str = f"{duration:.0f}m" if duration else "?"
        table.add_row(date_str, topic, dur_str, notes[:50] if notes else "")

    console.print(table)
