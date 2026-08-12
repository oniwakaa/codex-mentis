import sys
import readline
import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
from codex_mentis.core.config import load_config, CONFIG_DIR
from codex_mentis.cli.rich_ui import print_markdown, print_panel, create_spinner

DB_PATH = CONFIG_DIR / "memory.db"

# Try importing the actual agent orchestrator, fall back to a Socratic simulator
try:
    from codex_mentis.agents.orchestrator import orchestrate
except ImportError:
    # Socratic mock orchestrator
    def orchestrate(query: str, mode: str, topic: str, context: str = "") -> str:
        q = query.lower()
        
        # Save trace to L1 memory
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memory_entries (layer, content, topic, timestamp) VALUES (?, ?, ?, datetime('now'))",
                ("L1", f"User: {query}", topic)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
            
        if mode == "STUDY":
            if "pendulum" in topic.lower() or "lagrangian" in topic.lower():
                if "kinetic" in q or "t =" in q or "theta" in q:
                    return (
                        "Superb! The kinetic energy $T = \\frac{1}{2} m l^2 \\dot{\\theta}^2$ captures the rotational velocity. "
                        "Now, what is the potential energy $V(\\theta)$ if the pendulum of length $l$ hangs under gravity $g$?\n\n"
                        "*(Hint: Measure from the lowest point where $V = 0$)*"
                    )
                elif "potential" in q or "v =" in q or "cos" in q:
                    return (
                        "Exactly, $V(\\theta) = m g l (1 - \\cos\\theta)$.\n\n"
                        "We can now write the Lagrangian $L = T - V$:\n"
                        "$$L = \\frac{1}{2} m l^2 \\dot{\\theta}^2 - m g l (1 - \\cos\\theta)$$\n\n"
                        "What is the next step to derive the equation of motion using the Euler-Lagrange equations?"
                    )
            return (
                f"Welcome to study mode on **{topic}**! I'm your Socratic physics/math tutor agent.\n\n"
                "Let's break this down. What is your current understanding of the basic concepts here? "
                "Or would you like me to introduce a foundational question?"
            )
            
        elif mode == "EXPLORE":
            if "arxiv" in context.lower():
                return (
                    f"Let's explore: '{query}'. Based on the literature search, we have active discussions on this concept.\n\n"
                    "We can analyze the core claims and formulate a model. What specific hypothesis should we test first?"
                )
            return (
                f"Entering exploratory dive for: '{topic}'.\n\n"
                "Research shows that analyzing boundary constraints or extreme limits is a great way to build intuition. "
                "How does the system behave when parameters approach zero or infinity?"
            )
            
        # Default fallback conversation
        return (
            f"Received: '{query}' in {mode} mode concerning '{topic}'.\n\n"
            "To examine this mathematically, try typing `/verify <claim>` or `/plot <function>`."
        )

def save_repl_history() -> None:
    history_file = CONFIG_DIR / "repl_history"
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        readline.write_history_file(str(history_file))
    except Exception:
        pass

def load_repl_history() -> None:
    history_file = CONFIG_DIR / "repl_history"
    if history_file.exists():
        try:
            readline.read_history_file(str(history_file))
        except Exception:
            pass

def execute_slash_command(command_str: str, current_state: Dict[str, Any]) -> bool:
    """Executes a slash command. Returns True if REPL should continue, False if we should exit."""
    parts = command_str.split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    
    if cmd in ("/quit", "/exit"):
        save_repl_history()
        print_panel("Exiting Codex Mentis. Keep reasoning!", "Goodbye", style="green")
        return False
        
    elif cmd == "/help":
        help_text = (
            "Available Slash Commands:\n"
            "  /mode <MODE> <TOPIC>  - Switch mode (STUDY/EXPLORE/REASON) & topic\n"
            "  /verify <CLAIM>       - Run SymPy verification check\n"
            "  /plot <EXPR>          - Plot mathematical expression in terminal\n"
            "  /concept <SUB>        - View concept graph (map/status/next/review)\n"
            "  /memory <SUB>         - Query memory layers (show/search/clear/export)\n"
            "  /kb <SUB>             - Ingest or search knowledge bases\n"
            "  /skills <SUB>         - Manage prompts (list/show/evolve/install)\n"
            "  /clear                - Clear the screen\n"
            "  /help                 - Show this help dialogue\n"
            "  /quit or /exit        - Exit the REPL"
        )
        print_panel(help_text, "REPL Help Manual", style="magenta")
        
    elif cmd == "/clear":
        os.system('clear' if os.name == 'posix' else 'cls')
        
    elif cmd == "/mode":
        if not arg:
            print_panel("Usage: /mode <STUDY|EXPLORE|REASON> <topic>", "Error", style="red")
        else:
            mode_parts = arg.split(" ", 1)
            new_mode = mode_parts[0].upper()
            new_topic = mode_parts[1] if len(mode_parts) > 1 else "general"
            if new_mode not in ("STUDY", "EXPLORE", "REASON"):
                print_panel(f"Unknown mode: {new_mode}. Use STUDY, EXPLORE, or REASON.", "Error", style="red")
            else:
                current_state["mode"] = new_mode
                current_state["topic"] = new_topic
                print_panel(f"Switched to {new_mode} mode for: {new_topic}", "Mode Switch", style="cyan")
                
    elif cmd == "/verify":
        from codex_mentis.cli.commands.verify import verify
        try:
            verify(arg)
        except Exception as e:
            print_panel(f"Verification command failed: {e}", "Error", style="red")
            
    elif cmd == "/plot":
        from codex_mentis.cli.commands.visualize import plot_expression
        try:
            plot_expression(arg)
        except Exception as e:
            print_panel(f"Plotting command failed: {e}", "Error", style="red")
            
    elif cmd == "/concept":
        from codex_mentis.cli.commands.concept import app as concept_app
        # Run subcommands using Typer context runner or direct invocation
        subparts = arg.split(" ", 1)
        subcmd = subparts[0]
        subarg = subparts[1] if len(subparts) > 1 else ""
        
        if subcmd == "map":
            from codex_mentis.cli.commands.concept import show_map
            show_map(subarg if subarg else None)
        elif subcmd == "status":
            from codex_mentis.cli.commands.concept import show_status
            show_status()
        elif subcmd == "next":
            from codex_mentis.cli.commands.concept import suggest_next
            suggest_next()
        elif subcmd == "review":
            from codex_mentis.cli.commands.concept import show_review_queue
            show_review_queue()
        else:
            print_panel("Usage: /concept [map|status|next|review]", "Error", style="red")
            
    elif cmd == "/memory":
        subparts = arg.split(" ", 1)
        subcmd = subparts[0]
        subarg = subparts[1] if len(subparts) > 1 else ""
        
        if subcmd == "show":
            from codex_mentis.cli.commands.memory import show_memory
            show_memory(subarg if subarg else None)
        elif subcmd == "search":
            from codex_mentis.cli.commands.memory import search_memory
            search_memory(subarg)
        elif subcmd == "clear":
            from codex_mentis.cli.commands.memory import clear_memory
            clear_memory(subarg if subarg else "L1", force=True)
        elif subcmd == "export":
            from codex_mentis.cli.commands.memory import export_memory
            export_memory()
        else:
            print_panel("Usage: /memory [show|search|clear|export]", "Error", style="red")
            
    elif cmd == "/kb":
        subparts = arg.split(" ", 1)
        subcmd = subparts[0]
        subarg = subparts[1] if len(subparts) > 1 else ""
        
        if subcmd == "add":
            from codex_mentis.cli.commands.kb import add_document
            add_document(Path(subarg))
        elif subcmd == "list":
            from codex_mentis.cli.commands.kb import list_documents
            list_documents()
        elif subcmd == "search":
            from codex_mentis.cli.commands.kb import search_kb
            search_kb(subarg)
        else:
            print_panel("Usage: /kb [add|list|search]", "Error", style="red")
            
    elif cmd == "/skills":
        subparts = arg.split(" ", 1)
        subcmd = subparts[0]
        subarg = subparts[1] if len(subparts) > 1 else ""
        
        if subcmd == "list":
            from codex_mentis.cli.commands.skills import list_skills
            list_skills()
        elif subcmd == "show":
            from codex_mentis.cli.commands.skills import show_skill
            show_skill(subarg)
        elif subcmd == "evolve":
            from codex_mentis.cli.commands.skills import evolve_skill
            evolve_skill(subarg if subarg else None)
        elif subcmd == "install":
            from codex_mentis.cli.commands.skills import install_skill
            install_skill(subarg)
        else:
            print_panel("Usage: /skills [list|show|evolve|install]", "Error", style="red")
            
    else:
        print_panel(f"Unknown slash command: {cmd}", "Error", style="red")
        
    return True

def launch_repl(
    mode: str = "STUDY",
    topic: str = "general",
    context: str = "",
    domain: str = "general",
    difficulty: int = 2
) -> None:
    """Launch the interactive REPL shell."""
    current_state = {
        "mode": mode,
        "topic": topic,
        "context": context,
        "domain": domain,
        "difficulty": difficulty
    }
    
    load_repl_history()
    
    print_panel(
        f"Codex Mentis Interactive Agent Shell (v0.1.0)\n"
        f"Active Mode: [bold yellow]{current_state['mode']}[/bold yellow]\n"
        f"Topic: [bold green]{current_state['topic']}[/bold green]\n"
        f"Type [bold cyan]/help[/bold cyan] for commands, [bold cyan]/quit[/bold cyan] to exit.",
        "Codex Mentis",
        style="blue"
    )
    
    while True:
        try:
            # Build prompt indicator
            prompt = f"({current_state['mode']}:{current_state['topic']}) CM> "
            user_input = input(prompt).strip()
            
            if not user_input:
                continue
                
            # If user types a slash command
            if user_input.startswith("/"):
                should_continue = execute_slash_command(user_input, current_state)
                if not should_continue:
                    break
                continue
                
            # Otherwise, call orchestrator
            with create_spinner("Agent thinking...") as status:
                response = orchestrate(
                    query=user_input,
                    mode=current_state["mode"],
                    topic=current_state["topic"],
                    context=current_state["context"]
                )
                
            # Display response
            print_markdown(response)
            print()
            
        except (KeyboardInterrupt, EOFError):
            save_repl_history()
            print_panel("\nSession interrupted. Goodbye!", "Exiting", style="yellow")
            break
        except Exception as e:
            print_panel(f"An unexpected error occurred: {e}", "REPL Error", style="red")
