"""Doctor command — check system health and diagnose issues."""

import typer

from pitagora.core.constants import CONFIG_DIR

app = typer.Typer(help="System health checks and diagnostics")


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context):
    """Run system health checks."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    checks = []

    # 1. Check Python version
    import sys

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    checks.append(("Python ≥ 3.11", py_ok, py_ver))

    # 2. Check core dependencies
    deps = [
        ("typer", "typer"),
        ("rich", "rich"),
        ("sympy", "sympy"),
        ("numpy", "numpy"),
        ("httpx", "httpx"),
        ("pydantic", "pydantic"),
        ("yaml", "pyyaml"),
        ("sqlite_utils", "sqlite-utils"),
        ("plotext", "plotext"),
        ("matplotlib", "matplotlib"),
    ]
    for module, package in deps:
        try:
            __import__(module)
            checks.append((f"Package: {package}", True, "installed"))
        except ImportError:
            checks.append((f"Package: {package}", False, "MISSING"))

    # 3. Check optional dependencies
    optional_deps = [
        ("textual", "textual", "TUI interface"),
        ("sentence_transformers", "sentence-transformers", "Embeddings"),
        ("mcp", "mcp", "MCP integration"),
    ]
    for module, package, purpose in optional_deps:
        try:
            __import__(module)
            checks.append((f"Optional: {package}", True, f"installed ({purpose})"))
        except ImportError:
            checks.append((f"Optional: {package}", None, f"not installed ({purpose})"))

    # 4. Check config directory
    config_dir = CONFIG_DIR
    config_exists = config_dir.exists()
    checks.append(("Config directory", config_exists, str(config_dir)))

    if config_exists:
        config_file = config_dir / "config.yaml"
        checks.append(("Config file", config_file.exists(), str(config_file)))

        profile_file = config_dir / "profile.yaml"
        if profile_file.exists():
            checks.append(("User profile", True, str(profile_file)))
        else:
            checks.append(("User profile", None, "not created yet (run 'pitagora onboard')"))

    # 5. Check webfetch
    try:
        import webfetch  # noqa: F401

        checks.append(("webfetch (web search)", True, "installed — free web search enabled"))
    except ImportError:
        checks.append(
            ("webfetch (web search)", False, "MISSING — install: pip install webfetch-llm")
        )

    # 6. Check SymPy sandbox
    try:
        from pitagora.math_engine.sandbox import SymPySandbox

        sandbox = SymPySandbox()
        result = sandbox.evaluate("x**2 + 2*x + 1")
        sympy_ok = result.verified
        checks.append(("SymPy sandbox", sympy_ok, f"value={result.value}" if sympy_ok else "ERROR"))
    except Exception as e:
        checks.append(("SymPy sandbox", False, str(e)))

    # 7. Check database
    try:
        from pitagora.knowledge.base import KnowledgeBase

        kb = KnowledgeBase()
        stats = kb.get_stats()
        checks.append(
            ("Knowledge base", True, f"{stats['documents']} docs, {stats['chunks']} chunks")
        )
    except Exception as e:
        checks.append(("Knowledge base", False, str(e)))

    # Render results
    table = Table(title="🏥 Pitagora Health Check", show_header=True, show_lines=True)
    table.add_column("Check", style="bold", min_width=25)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Details", min_width=30)

    all_ok = True
    for name, status, detail in checks:
        if status is True:
            table.add_row(name, "[green]✓ OK[/green]", detail)
        elif status is False:
            table.add_row(name, "[red]✗ FAIL[/red]", f"[red]{detail}[/red]")
            all_ok = False
        else:
            table.add_row(name, "[dim]— SKIP[/dim]", f"[dim]{detail}[/dim]")

    console.print(table)

    if all_ok:
        console.print(
            Panel(
                "[green]All systems operational! Pitagora is ready.[/green]",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[yellow]Some checks failed. Install missing packages with:[/yellow]\n"
                "  pip install pitagora[all]",
                border_style="yellow",
            )
        )
