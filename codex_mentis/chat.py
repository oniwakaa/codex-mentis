"""Interactive chat REPL — the main user experience.

This is the core chat loop. It connects to the configured provider and provides
a conversational interface for studying math/physics.
"""
import os
import sys
import asyncio
from typing import Optional, Dict, Any

import httpx


def load_provider_config() -> Dict[str, Any]:
    """Load provider configuration from config.yaml or environment."""
    from pathlib import Path
    import yaml

    config_path = Path("~/.codex-mentis/config.yaml").expanduser()
    
    # Try config file
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        providers = config.get("providers", {})
        provider_config = providers.get("config", {})
        if provider_config:
            return provider_config

    # Try environment variables (CLIProxy)
    api_key = os.getenv("OPENAI_API_KEY", os.getenv("CLIPROXY_API_KEY", ""))
    base_url = os.getenv("OPENAI_BASE_URL", "")
    
    if base_url and api_key:
        return {
            "name": "cliproxy",
            "type": "openai_compatible",
            "base_url": base_url,
            "api_key": api_key,
            "default_model": os.getenv("CM_MODEL", "google/gemini-3.6-flash-high"),
        }

    # Try CLIProxy defaults
    return {
        "name": "cliproxy",
        "type": "openai_compatible",
        "base_url": "http://localhost:8317/v1",
        "api_key": "cliproxy-sk-local",
        "default_model": "google/gemini-3.6-flash-high",
    }


def chat_completion(
    messages: list,
    model: Optional[str] = None,
    config: Optional[Dict] = None,
    stream: bool = False,
) -> str:
    """Send a chat completion request and return the response."""
    if config is None:
        config = load_provider_config()

    base_url = config.get("base_url", "http://localhost:8317/v1")
    api_key = config.get("api_key", "cliproxy-sk-local")
    model = model or config.get("default_model", "google/gemini-3.6-flash-high")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.7,
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content
    except httpx.ConnectError:
        return "[Error: Cannot connect to API. Is CLIProxy running? Try `codex-mentis setup` to reconfigure.]"
    except httpx.TimeoutException:
        return "[Error: Request timed out. The model may be overloaded.]"
    except Exception as e:
        return f"[Error: {e}]"


def launch_chat(
    mode: str = "study",
    topic: str = "general",
    system_prompt: Optional[str] = None,
) -> None:
    """Launch the interactive chat REPL."""
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    config = load_provider_config()
    model = config.get("default_model", "unknown")

    # System prompt for the tutor
    if system_prompt is None:
        system_prompt = (
            "You are Codex Mentis, an expert mathematics and physics tutor. "
            "You explain concepts clearly using the Socratic method — ask guiding questions "
            "before giving answers. Use LaTeX notation for equations ($..$ inline, $$...$$ display). "
            "Be precise, rigorous, and encouraging. When a student makes a mistake, "
            "guide them to discover the error rather than just correcting it. "
            "Use markdown formatting for structure."
        )

    messages = [{"role": "system", "content": system_prompt}]

    # Welcome
    console.print(Panel(
        f"[bold cyan]Codex Mentis[/bold cyan] — {mode.title()} mode\n"
        f"Model: [dim]{model}[/dim]\n"
        f"Topic: [dim]{topic}[/dim]\n\n"
        f"Type your question or topic. Commands:\n"
        f"  [cyan]/mode <study|explore|reason|verify>[/cyan]  Switch mode\n"
        f"  [cyan]/topic <name>[/cyan]                        Change topic\n"
        f"  [cyan]/clear[/cyan]                               Clear history\n"
        f"  [cyan]/quit[/cyan]                                Exit\n",
        title="🧠 Codex Mentis",
        border_style="blue",
    ))

    while True:
        try:
            # Prompt
            prompt_text = f"({mode}:{topic}) 🧠 "
            user_input = console.input(f"[bold green]{prompt_text}[/bold green]")
            
            if not user_input.strip():
                continue

            # Handle commands
            if user_input.strip().startswith("/"):
                cmd_parts = user_input.strip().split(" ", 1)
                cmd = cmd_parts[0].lower()
                arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

                if cmd in ("/quit", "/exit", "/q"):
                    console.print("[dim]Goodbye! Keep reasoning.[/dim]")
                    break
                elif cmd == "/clear":
                    messages = [{"role": "system", "content": system_prompt}]
                    console.print("[dim]Conversation cleared.[/dim]")
                    continue
                elif cmd == "/mode":
                    if arg:
                        mode = arg.strip()
                        console.print(f"[dim]Switched to {mode} mode.[/dim]")
                    continue
                elif cmd == "/topic":
                    if arg:
                        topic = arg.strip()
                        console.print(f"[dim]Topic set to: {topic}[/dim]")
                    continue
                elif cmd == "/model":
                    if arg:
                        config["default_model"] = arg.strip()
                        model = arg.strip()
                        console.print(f"[dim]Model: {model}[/dim]")
                    continue
                elif cmd == "/help":
                    console.print(Panel(
                        "[bold]Commands:[/bold]\n"
                        "  /mode <mode>    Switch mode (study/explore/reason/verify)\n"
                        "  /topic <name>   Change topic\n"
                        "  /model <name>   Change model\n"
                        "  /clear          Clear conversation\n"
                        "  /quit           Exit\n"
                        "  /help           Show this help\n\n"
                        "[bold]Tips:[/bold]\n"
                        "  Ask anything about math or physics!\n"
                        "  The tutor uses Socratic method — expect guiding questions.\n"
                        "  Use $..$ for inline math, $$...$$ for display math.",
                        title="Help",
                        border_style="cyan",
                    ))
                    continue
                else:
                    console.print(f"[dim]Unknown command: {cmd}. Type /help for commands.[/dim]")
                    continue

            # Add context about mode and topic
            context_msg = f"[Context: Mode={mode}, Topic={topic}] {user_input}"
            messages.append({"role": "user", "content": context_msg})

            # Get response
            with console.status("[bold cyan]Thinking...[/bold cyan]"):
                response = chat_completion(messages, model=model, config=config)

            # Display response
            messages.append({"role": "assistant", "content": response})
            console.print()
            console.print(Markdown(response))
            console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Use /quit to exit.[/dim]")
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break
