"""Data CLI — load, profile, analyze, and plot datasets.

pitagora data load <path_or_url>
pitagora data profile
pitagora data analyze "question"
pitagora data plot <type> [--x ...] [--y ...] [--save PATH]
"""

import typer

from pitagora.cli.rich_ui import print_panel, print_table

app = typer.Typer(help="Load, profile, analyze, and visualize datasets")

# ponytail: a single in-process dataset handle is enough for the CLI. The
# data agent keeps its own registry for interactive use; here we just hold
# one loaded DataFrame between subcommands via a module global. Upgrade to a
# session-backed store if the CLI needs multiple concurrent datasets.
_LOADED: dict = {}


def _load_or_exit(path_or_url: str):
    from pitagora.data_analysis.loader import LoaderError, load_data

    try:
        return load_data(path_or_url)
    except LoaderError as e:
        typer.echo(f"Load error: {e}")
        raise typer.Exit(1)


@app.command("load")
def load_cmd(
    path_or_url: str = typer.Argument(..., help="File path or URL"),
):
    """Load and auto-profile a dataset."""
    df = _load_or_exit(path_or_url)
    _LOADED["df"] = df
    from pitagora.data_analysis.profiler import profile_data

    prof = profile_data(df)
    typer.echo(f"Loaded {prof.rows} rows × {prof.cols} cols")
    rows = [
        [
            c.name,
            c.inferred_type,
            str(c.missing_count),
            str(c.cardinality),
            f"{c.mean:.3f}" if c.mean is not None else "-",
        ]
        for c in prof.columns
    ]
    print_table(
        ["Column", "Type", "Missing", "Cardinality", "Mean"], rows, title=f"Profile: {path_or_url}"
    )


@app.command("profile")
def profile_cmd(
    path_or_url: str | None = typer.Option(None, "--path", "-p", help="Dataset path (reloads)"),
):
    """Show the full profile of a loaded (or reloaded) dataset."""
    if path_or_url:
        _LOADED["df"] = _load_or_exit(path_or_url)
    df = _LOADED.get("df")
    if df is None:
        typer.echo("No dataset loaded. Use `pitagora data load <path>` or `--path`.")
        raise typer.Exit(1)
    from pitagora.data_analysis.profiler import profile_data

    prof = profile_data(df)
    lines = [f"Rows: {prof.rows}  Cols: {prof.cols}"]
    for c in prof.columns:
        line = f"  {c.name} ({c.inferred_type}): missing={c.missing_count} ({c.missing_pct:.1%}), card={c.cardinality}"
        if c.mean is not None:
            line += f", mean={c.mean:.3f}, std={c.std:.3f}, min={c.min:.3f}, max={c.max:.3f}"
            if c.skewness is not None:
                line += f", skew={c.skewness:.3f}"
        lines.append(line)
    if prof.correlation:
        lines.append("Correlation:")
        for a, row in prof.correlation.items():
            for b, v in row.items():
                if a < b and abs(v) >= 0.5:
                    lines.append(f"  {a} ↔ {b}: {v:.3f}")
    print_panel("\n".join(lines), title="Dataset Profile", style="cyan")


@app.command("analyze")
def analyze_cmd(
    question: str = typer.Argument(..., help="Analytical question"),
    path_or_url: str | None = typer.Option(None, "--path", "-p", help="Dataset path"),
):
    """Interactive analysis — the agent decides and runs the appropriate test."""
    from rich.console import Console
    from rich.markdown import Markdown

    from pitagora.chat import chat_completion, load_provider_config

    console = Console()
    df = _LOADED.get("df")
    if path_or_url:
        df = _load_or_exit(path_or_url)
        _LOADED["df"] = df
    if df is None:
        typer.echo("No dataset loaded. Use `pitagora data load <path>` or `--path`.")
        raise typer.Exit(1)

    from pitagora.data_analysis.profiler import profile_data

    prof = profile_data(df)
    context = (
        f"Dataset profile: {prof.rows} rows × {prof.cols} cols.\n"
        f"Columns: {[(c.name, c.inferred_type) for c in prof.columns]}\n"
        f"Question: {question}\n\n"
        f"Recommend and explain an appropriate analysis. Describe the steps and "
        f"what result to expect. Do not invent numbers — describe the method."
    )
    config = load_provider_config()
    messages = [
        {"role": "system", "content": "You are Pitagora, a statistical data analyst."},
        {"role": "user", "content": context},
    ]
    with console.status("[cyan]Analyzing...[/cyan]"):
        response = chat_completion(messages, config=config)
    console.print(Markdown(response))


@app.command("plot")
def plot_cmd(
    plot_type: str = typer.Argument("hist", help="line | scatter | hist | bar"),
    x: str | None = typer.Option(None, "--x", help="X column"),
    y: str | None = typer.Option(None, "--y", help="Y column"),
    save: str | None = typer.Option(None, "--save", help="Save PNG to path"),
    path_or_url: str | None = typer.Option(None, "--path", "-p", help="Dataset path"),
):
    """Generate a visualization for a loaded dataset."""
    if path_or_url:
        _LOADED["df"] = _load_or_exit(path_or_url)
    df = _LOADED.get("df")
    if df is None:
        typer.echo("No dataset loaded. Use `pitagora data load <path>` or `--path`.")
        raise typer.Exit(1)
    from pitagora.data_analysis.visualizer import create_plot

    out = create_plot(df, plot_type=plot_type, x=x, y=y, save_path=save)
    typer.echo(out)
