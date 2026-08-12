"""Folder ingestion — analyze papers, books, and documents in a directory."""
import os
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Ingest and analyze documents from folders")


@app.command("ingest")
def ingest_folder(
    path: str = typer.Argument(..., help="Path to folder or file to ingest"),
    subject: str = typer.Option("general", "--subject", "-s", help="Subject tag for all documents"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r", help="Scan subdirectories"),
    stats: bool = typer.Option(False, "--stats", help="Show knowledge base statistics instead of ingesting"),
    search: Optional[str] = typer.Option(None, "--search", help="Search ingested documents"),
):
    """Ingest documents from a folder into the knowledge base.

    Supports: PDF, Markdown, LaTeX, plain text, Jupyter notebooks.
    Extracts text, chunks it, and stores with citations for RAG retrieval.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskProgressColumn
    from rich.table import Table

    console = Console()

    if stats:
        _show_stats(console)
        return

    if search:
        _search_docs(console, search)
        return

    target = Path(path).expanduser()
    if not target.exists():
        console.print(f"[red]Error: Path not found: {target}[/red]")
        raise typer.Exit(1)

    # Collect files
    extensions = {".pdf", ".md", ".markdown", ".tex", ".latex", ".txt", ".rst", ".ipynb", ".html", ".htm"}
    files = []
    if target.is_file():
        files = [target]
    else:
        pattern = "**/*" if recursive else "*"
        for f in target.glob(pattern):
            if f.is_file() and f.suffix.lower() in extensions:
                files.append(f)

    if not files:
        console.print(f"[yellow]No supported documents found in {target}[/yellow]")
        console.print(f"[dim]Supported formats: {', '.join(sorted(extensions))}[/dim]")
        return

    console.print(Panel(
        f"Found [bold cyan]{len(files)}[/bold cyan] documents to ingest\n"
        f"Subject: [cyan]{subject}[/cyan]\n"
        f"Path: [cyan]{target}[/cyan]",
        title="📥 Document Ingestion",
        border_style="blue",
    ))

    # Ingest
    from codex_mentis.knowledge.base import KnowledgeBase
    from codex_mentis.knowledge.ingester import DocumentIngester
    from codex_mentis.knowledge.chunker import SmartChunker

    kb = KnowledgeBase()
    ingester = DocumentIngester()
    chunker = SmartChunker()

    success = 0
    failed = 0
    total_chunks = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting...", total=len(files))

        for f in files:
            progress.update(task, description=f"[cyan]{f.name}[/cyan]")
            
            try:
                # Check if already ingested
                existing = kb.search(f.name, limit=1)
                if existing and existing[0].get("source") == str(f):
                    progress.advance(task)
                    continue

                # Extract text
                text = ingester.extract_text(str(f))
                if not text or len(text.strip()) < 50:
                    failed += 1
                    progress.advance(task)
                    continue

                # Chunk
                chunks = chunker.chunk_text(text, source=str(f))
                
                # Store
                kb.add_document(
                    path=str(f),
                    title=f.stem,
                    subject=subject,
                    chunks=chunks,
                    metadata={"file_size": f.stat().st_size, "extension": f.suffix},
                )

                success += 1
                total_chunks += len(chunks)
            except Exception as e:
                failed += 1

            progress.advance(task)

    # Summary
    console.print(Panel(
        f"[green]✓ {success} documents ingested successfully[/green]\n"
        f"[red]✗ {failed} failed[/red]\n"
        f"[cyan]📦 {total_chunks} chunks created[/cyan]\n\n"
        f"[dim]Search with: codex-mentis ingest --search \"your query\"[/dim]",
        title="📥 Ingestion Complete",
        border_style="green" if failed == 0 else "yellow",
    ))


def _show_stats(console):
    """Show knowledge base statistics."""
    from rich.table import Table
    from codex_mentis.knowledge.base import KnowledgeBase

    kb = KnowledgeBase()
    stats = kb.get_stats()

    table = Table(title="📊 Knowledge Base Statistics", show_header=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Documents", str(stats["documents"]))
    table.add_row("Chunks", str(stats["chunks"]))

    for subj, count in stats.get("subjects", {}).items():
        table.add_row(f"  Subject: {subj}", str(count))

    console.print(table)


def _search_docs(console, query: str):
    """Search ingested documents."""
    from rich.markdown import Markdown
    from rich.panel import Panel
    from codex_mentis.knowledge.base import KnowledgeBase

    kb = KnowledgeBase()
    results = kb.search(query, limit=5)

    if not results:
        console.print(f"[yellow]No results for: {query}[/yellow]")
        return

    console.print(f"[bold]Search results for:[/bold] {query}\n")
    for i, r in enumerate(results, 1):
        console.print(Panel(
            f"**Source:** {r.get('source', 'Unknown')}\n"
            f"**Subject:** {r.get('subject', 'General')}\n\n"
            f"{r.get('content', '')[:500]}",
            title=f"Result {i}",
            border_style="cyan",
        ))
