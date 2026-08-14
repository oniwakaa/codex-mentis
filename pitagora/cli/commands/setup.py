"""Setup wizard — configure providers, API keys, and preferences interactively."""

import os
from typing import Any

import typer

from pitagora.core.constants import CONFIG_DIR, CONFIG_PATH

app = typer.Typer(help="Configure Pitagora providers and settings")


@app.callback(invoke_without_command=True)
def setup_main(ctx: typer.Context):
    """Interactive setup wizard for first-time configuration."""
    if ctx.invoked_subcommand is not None:
        return
    run_setup()


def run_setup(console=None, quick: bool = False):
    """Run the interactive setup wizard."""
    import yaml
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt

    if console is None:
        console = Console()

    console.print(
        Panel(
            "[bold cyan]⚙️  Pitagora Setup Wizard[/bold cyan]\n\n"
            "Configure your AI providers, model preferences, and features.\n"
            "You can always re-run this with `pitagora setup`.",
            border_style="cyan",
        )
    )

    config_dir = CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = CONFIG_PATH

    # Load existing config if any
    existing = {}
    if config_path.exists():
        with open(config_path) as f:
            existing = yaml.safe_load(f) or {}

    # ─── Step 1: Provider Selection ───
    console.print("\n[bold]Step 1: Choose your AI provider[/bold]\n")
    console.print("  [cyan]1[/cyan] = CLIProxy (local proxy, recommended)")
    console.print("  [cyan]2[/cyan] = OpenAI (GPT-4o, GPT-4)")
    console.print("  [cyan]3[/cyan] = Anthropic (Claude)")
    console.print("  [cyan]4[/cyan] = Google Gemini (direct API)")
    console.print("  [cyan]5[/cyan] = Ollama (local models)")
    console.print("  [cyan]6[/cyan] = Custom (OpenAI-compatible endpoint)")

    choice = Prompt.ask(
        "Provider", choices=["1", "2", "3", "4", "5", "6"], default="1" if quick else None
    )

    providers_config = _configure_provider(choice, console, existing)

    # ─── Step 2: Model Selection ───
    console.print("\n[bold]Step 2: Choose default model[/bold]\n")

    default_model = providers_config.get("default_model", "")
    if not default_model:
        if choice == "1":
            console.print("  Recommended: [cyan]google/gemini-3.6-flash-high[/cyan]")
            console.print(
                "  Also available: google/gemini-3.6-high, google/gemini-3.5-flash-medium"
            )
            default_model = Prompt.ask("Model", default="google/gemini-3.6-flash-high")
        elif choice == "2":
            default_model = Prompt.ask("Model", default="gpt-4o")
        elif choice == "3":
            default_model = Prompt.ask("Model", default="claude-sonnet-4-20250514")
        elif choice == "4":
            default_model = Prompt.ask("Model", default="gemini-1.5-pro")
        elif choice == "5":
            default_model = Prompt.ask("Model", default="llama3")
        else:
            default_model = Prompt.ask("Model name", default="gpt-4o")

    # ─── Step 3: Features ───
    console.print("\n[bold]Step 3: Features[/bold]\n")

    enable_embeddings = Confirm.ask("Enable vector embeddings for semantic search?", default=True)
    enable_spaced_rep = Confirm.ask("Enable spaced repetition?", default=True)

    # ─── Step 4: MCP servers ───
    console.print("\n[bold]Step 4: Configure MCP servers[/bold]\n")
    _configure_mcp(console)

    # ─── Step 5: Skill packs ───
    console.print("\n[bold]Step 5: Install skill packs[/bold]\n")
    _select_skill_packs(console)

    # ─── Step 6: Build config ───
    config = {
        "providers": {
            "default": providers_config.get("name", "cliproxy"),
            "config": providers_config,
        },
        "model": default_model,
        "features": {
            "embeddings": enable_embeddings,
            "spaced_repetition": enable_spaced_rep,
        },
        "memory": {
            "backend": "sqlite",
            "spaced_repetition": enable_spaced_rep,
        },
        "ui": {
            "theme": "dark",
            "latex": True,
        },
    }

    # Write config
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # ─── Step 5: Verify ───
    console.print("\n[bold]Step 4: Verification[/bold]\n")
    _verify_connection(providers_config, default_model, console)

    # ─── Done ───
    console.print(
        Panel(
            f"[green]✓ Configuration saved to {config_path}[/green]\n\n"
            f"Provider: [cyan]{providers_config.get('name', 'cliproxy')}[/cyan]\n"
            f"Model: [cyan]{default_model}[/cyan]\n"
            f"Embeddings: [cyan]{'enabled' if enable_embeddings else 'disabled'}[/cyan]\n"
            f"Spaced Repetition: [cyan]{'enabled' if enable_spaced_rep else 'disabled'}[/cyan]\n\n"
            "[bold]Get started:[/bold]\n"
            "  pitagora                    Launch the interactive chat\n"
            "  pitagora onboard            Set up your learning profile\n"
            '  pitagora study "calculus"   Start learning\n'
            "  pitagora doctor             Check system health",
            title="✅ Setup Complete",
            border_style="green",
        )
    )


def _configure_provider(choice: str, console, existing: dict) -> dict[str, Any]:
    """Configure a specific provider and return its config dict."""
    from rich.prompt import Prompt

    if choice == "1":  # CLIProxy
        api_url = Prompt.ask("CLIProxy API URL", default="http://localhost:8317/v1")
        api_key = Prompt.ask("API Key", default="cliproxy-sk-local")

        config = {
            "name": "cliproxy",
            "type": "openai_compatible",
            "base_url": api_url,
            "api_key": api_key,
            "default_model": "google/gemini-3.6-flash-high",
        }

        # Set environment variable
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_BASE_URL"] = api_url

        console.print(f"  [green]✓[/green] CLIProxy configured at {api_url}")
        return config

    elif choice == "2":  # OpenAI
        api_key = Prompt.ask("OpenAI API Key", default=os.getenv("OPENAI_API_KEY", ""))
        config = {
            "name": "openai",
            "type": "openai",
            "api_key": api_key,
            "default_model": "",
        }
        os.environ["OPENAI_API_KEY"] = api_key
        console.print("  [green]✓[/green] OpenAI configured")
        return config

    elif choice == "3":  # Anthropic
        api_key = Prompt.ask("Anthropic API Key", default=os.getenv("ANTHROPIC_API_KEY", ""))
        config = {
            "name": "anthropic",
            "type": "anthropic",
            "api_key": api_key,
            "default_model": "",
        }
        os.environ["ANTHROPIC_API_KEY"] = api_key
        console.print("  [green]✓[/green] Anthropic configured")
        return config

    elif choice == "4":  # Gemini direct
        api_key = Prompt.ask(
            "Google API Key", default=os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))
        )
        config = {
            "name": "gemini",
            "type": "gemini",
            "api_key": api_key,
            "default_model": "",
        }
        os.environ["GEMINI_API_KEY"] = api_key
        console.print("  [green]✓[/green] Gemini configured")
        return config

    elif choice == "5":  # Ollama
        base_url = Prompt.ask("Ollama URL", default="http://localhost:11434")
        config = {
            "name": "ollama",
            "type": "ollama",
            "base_url": base_url,
            "api_key": "ollama",
            "default_model": "",
        }
        console.print(f"  [green]✓[/green] Ollama configured at {base_url}")
        return config

    else:  # Custom
        base_url = Prompt.ask("API Base URL (OpenAI-compatible)")
        api_key = Prompt.ask("API Key")
        name = Prompt.ask("Provider name", default="custom")
        config = {
            "name": name,
            "type": "openai_compatible",
            "base_url": base_url,
            "api_key": api_key,
            "default_model": "",
        }
        console.print(f"  [green]✓[/green] Custom provider '{name}' configured")
        return config


def _configure_mcp(console) -> None:
    """Toggle MCP servers and write ~/.pitagora/mcp.json."""
    from rich.prompt import Prompt

    from pitagora.mcp_integration import MCPManager

    mgr = MCPManager()
    servers = list(mgr.servers.items())
    for i, (name, srv) in enumerate(servers, 1):
        mark = "[green]x[/green]" if srv.enabled else " "
        console.print(f"  [{mark}] [cyan]{i}[/cyan] = {name:<20} {srv.description}")

    console.print("  Toggle servers by number (comma-separated), or Enter to continue.")
    choice = Prompt.ask("Servers", default="")
    if choice.strip():
        for tok in choice.split(","):
            tok = tok.strip()
            if tok.isdigit():
                idx = int(tok) - 1
                if 0 <= idx < len(servers):
                    name = servers[idx][0]
                    mgr.set_enabled(name, not mgr.servers[name].enabled)

    path = mgr.save_config()
    enabled = [n for n, s in mgr.servers.items() if s.enabled]
    console.print(f"  [green]✓[/green] MCP config saved to {path}")
    console.print(f"  [dim]Enabled: {', '.join(enabled) or 'none'}[/dim]")


def _select_skill_packs(console) -> None:
    """Show builtin skill packs and their counts."""
    from pitagora.skills.engine import SkillsEngine

    eng = SkillsEngine()
    packs: dict[str, int] = {}
    for name in eng.list_skills():
        try:
            skill = eng.load_skill(name)
            packs[skill.domain] = packs.get(skill.domain, 0) + 1
        except Exception:
            continue
    for i, (domain, count) in enumerate(sorted(packs.items()), 1):
        console.print(f"  [green]x[/green] [cyan]{i}[/cyan] = {domain:<20} {count} skill(s)")
    console.print(
        "  [dim]All builtin skills are available by default. Use `pitagora skills list` to inspect.[/dim]"
    )


def _verify_connection(config: dict, model: str, console):
    """Try a test completion to verify the provider works."""
    import httpx

    base_url = config.get("base_url", "")
    api_key = config.get("api_key", "")

    if not base_url or not api_key:
        console.print("  [yellow]⚠ Skipping verification (no URL/key)[/yellow]")
        return

    console.print("  Testing connection...", end=" ")

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Say 'hello' in one word."}],
                    "max_tokens": 10,
                },
            )

        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            console.print(f"[green]✓ Connected! Response: '{content.strip()}'[/green]")
        else:
            console.print(
                f"[yellow]⚠ Got status {response.status_code}: {response.text[:100]}[/yellow]"
            )
    except Exception as e:
        console.print(f"[red]✗ Connection failed: {e}[/red]")
        console.print(
            "  [dim]You can still use Pitagora — configure the provider later with `pitagora setup`[/dim]"
        )
