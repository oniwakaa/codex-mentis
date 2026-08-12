import typer
from codex_mentis.cli.commands import (
    study,
    explore,
    reason,
    verify,
    visualize,
    concept,
    memory,
    kb,
    config,
    skills
)

app = typer.Typer(
    name="codex-mentis",
    help="Codex Mentis: A CLI tool for studying math and physics with AI agents",
    no_args_is_help=False
)

# Register command groups (Sub-apps)
app.add_typer(concept.app, name="concept")
app.add_typer(memory.app, name="memory")
app.add_typer(kb.app, name="kb")
app.add_typer(config.app, name="config")
app.add_typer(skills.app, name="skills")

# Register single commands
app.command("study")(study.study)
app.command("explore")(explore.explore)
app.command("derive")(reason.derive)
app.command("verify")(verify.verify)
app.command("plot")(visualize.plot_expression)

@app.command("chat")
def chat_cmd():
    """Launch the interactive REPL shell."""
    from codex_mentis.cli.repl import launch_repl
    launch_repl()

@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Entrypoint callback which boots the REPL if no subcommand is executed."""
    if ctx.invoked_subcommand is None:
        from codex_mentis.cli.repl import launch_repl
        launch_repl()

if __name__ == "__main__":
    app()
