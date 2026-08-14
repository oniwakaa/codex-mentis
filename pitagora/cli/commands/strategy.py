"""Strategy CLI — report pedagogical strategy metrics and weekly-style digests.

Surfaces the SelfImprover's `strategy_report` and `digest` methods so the
feedback loop is observable from the command line.
"""

import typer

from pitagora.cli.rich_ui import print_panel, print_table

app = typer.Typer(help="Self-improving strategy metrics and digests")


def _improver():
    """Build a SelfImproverAgent using the configured provider (best-effort).

    ponytail: strategy metrics live in the local SQLite DB and do not require
    a live LLM to report. We still construct the agent for its DB methods; if
    provider config is missing we fall back to a mock provider so the CLI works
    offline. Upgrade path: reuse the shared provider loader when it's reliable
    in all environments.
    """
    from pitagora.agents.providers.base import BaseProvider, ProviderConfig
    from pitagora.agents.self_improver import SelfImproverAgent

    class _NullProvider(BaseProvider):
        def __init__(self):
            super().__init__(ProviderConfig(api_key="null", model="null"))

        def complete(self, messages, tools=None, temperature=0.7, response_format=None):
            return {"content": "", "tool_calls": []}

        async def acomplete(self, messages, tools=None, temperature=0.7, response_format=None):
            return {"content": "", "tool_calls": []}

        def stream(self, messages):
            yield ""

        async def astream(self, messages):
            yield ""

        def embed(self, texts):
            return [[0.0] for _ in texts]

        async def aembed(self, texts):
            return [[0.0] for _ in texts]

    return SelfImproverAgent(_NullProvider())


@app.command("report")
def strategy_report(
    topic: str | None = typer.Option(None, "--topic", "-t", help="Filter by topic"),
    level: str | None = typer.Option(None, "--level", "-l", help="Filter by level"),
    last_n: int | None = typer.Option(
        None, "--last", "-n", help="Only consider the last N interactions"
    ),
):
    """Aggregate performance metrics per strategy (optionally filtered)."""
    improver = _improver()
    rows = improver.strategy_report(topic=topic, level=level, last_n=last_n)
    if not rows:
        typer.echo("No strategy metrics recorded yet.")
        return
    table_rows = []
    for r in rows:
        table_rows.append(
            [
                r.get("strategy_used", "?"),
                str(r.get("uses", 0)),
                f"{r.get('avg_quality', 0):.2f}" if r.get("avg_quality") is not None else "-",
                f"{r.get('avg_hints', 0):.2f}" if r.get("avg_hints") is not None else "-",
                f"{r.get('success_rate', 0) * 100:.0f}%",
            ]
        )
    print_table(
        ["Strategy", "Uses", "Avg Quality", "Avg Hints", "Success"],
        table_rows,
        title="Strategy Report",
    )


@app.command("digest")
def digest():
    """Print a weekly-style digest: top/bottom strategies, trending topics, focus."""
    improver = _improver()
    d = improver.digest()
    if not d.get("top") and not d.get("bottom"):
        typer.echo("No data for digest yet.")
        return

    lines = []
    if d.get("top"):
        lines.append("[bold green]Top strategies[/bold green]")
        for r in d["top"]:
            lines.append(
                f"  • {r.get('strategy_used', '?')}: "
                f"avg {r.get('avg_quality', 0):.2f}, "
                f"{r.get('success_rate', 0) * 100:.0f}% success"
            )
    if d.get("bottom"):
        lines.append("[bold red]Bottom strategies[/bold red]")
        for r in d["bottom"]:
            lines.append(
                f"  • {r.get('strategy_used', '?')}: "
                f"avg {r.get('avg_quality', 0):.2f}, "
                f"{r.get('success_rate', 0) * 100:.0f}% success"
            )
    if d.get("trending"):
        lines.append("[bold cyan]Trending topics[/bold cyan]")
        for t in d["trending"]:
            lines.append(f"  • {t.get('topic', '?')}: {t.get('uses', 0)} uses")
    if d.get("focus"):
        lines.append("[bold yellow]Focus areas[/bold yellow]")
        lines.append("  " + ", ".join(d["focus"]))
    print_panel("\n".join(lines), title="Weekly Digest", style="cyan")
