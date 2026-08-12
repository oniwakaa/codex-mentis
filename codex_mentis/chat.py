"""Interactive chat REPL — the main user experience.

This is the core chat loop. It connects ALL systems:
- Provider (CLIProxy/Gemini/OpenAI/etc)
- Knowledge base (RAG — inject relevant context)
- Concept graph (track what user studies)
- User graph (personalize by level/mastery)
- SymPy sandbox (verify math claims)
- Memory (save/load conversations)
- Spaced repetition (trigger reviews)
"""
import os
import sys
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx


def load_provider_config() -> Dict[str, Any]:
    """Load provider configuration from config.yaml or environment."""
    from pathlib import Path
    import yaml

    config_path = Path("~/.codex-mentis/config.yaml").expanduser()
    
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        providers = config.get("providers", {})
        provider_config = providers.get("config", {})
        if provider_config:
            return provider_config

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


def _get_rag_context(query: str, max_tokens: int = 2000) -> str:
    """Retrieve relevant context from knowledge base for RAG."""
    try:
        from codex_mentis.knowledge.base import KnowledgeBase
        kb = KnowledgeBase()
        results = kb.search(query, limit=3)
        if not results:
            return ""
        
        context_parts = ["[Relevant knowledge from your documents:]"]
        for r in results:
            source = r.get("source", "Unknown")
            content = r.get("content", "")[:500]
            context_parts.append(f"- [{source}]: {content}")
        
        return "\n".join(context_parts)
    except Exception:
        return ""


def _get_concept_context(topic: str) -> str:
    """Get concept graph context — prerequisites, learning path."""
    try:
        from codex_mentis.concepts.graph import ConceptGraph
        cg = ConceptGraph()
        
        # Check if topic exists in graph
        if topic.lower() in [k.lower() for k in cg.graph.keys()]:
            prereqs = cg.get_prerequisites(topic)
            path = cg.get_learning_path(topic)
            if prereqs or path:
                parts = [f"[Concept graph for '{topic}':]"]
                if prereqs:
                    parts.append(f"  Prerequisites: {', '.join(prereqs)}")
                if path:
                    parts.append(f"  Learning path: {' → '.join(path[:5])}")
                return "\n".join(parts)
    except Exception:
        pass
    return ""


def _get_user_context() -> str:
    """Get user profile context — level, mastery, recent activity."""
    try:
        from codex_mentis.cli.commands.onboard import load_profile
        profile = load_profile()
        if not profile:
            return ""
        
        parts = [f"[User profile: {profile.get('name', 'Student')}]"]
        levels = profile.get("levels", {})
        for subj, level in levels.items():
            parts.append(f"  {subj}: {level}")
        
        interests = profile.get("interests", [])
        if interests:
            parts.append(f"  Interests: {', '.join(interests)}")
        
        return "\n".join(parts)
    except Exception:
        return ""


def _verify_math(response: str) -> Optional[str]:
    """Check if response contains math claims and verify with SymPy."""
    import re
    
    # Look for simple equations in the response
    equations = re.findall(r'\$([^$]+)\$', response)
    if not equations:
        return None
    
    try:
        from codex_mentis.math_engine.sandbox import SymPySandbox
        sandbox = SymPySandbox()
        
        verified = []
        for eq in equations[:3]:  # Check up to 3 equations
            # Try to evaluate
            result = sandbox.evaluate(eq)
            if result.verified:
                verified.append(f"  ✓ {eq} = {result.value}")
            elif result.error:
                verified.append(f"  ⚠ {eq}: {result.error}")
        
        if verified:
            return "[SymPy verification:]\n" + "\n".join(verified)
    except Exception:
        pass
    return None


def _save_to_memory(role: str, content: str, topic: str = "general") -> None:
    """Save message to memory store."""
    try:
        from codex_mentis.memory.store import MemoryStore
        from codex_mentis.core.models import MemoryEntry
        store = MemoryStore()
        entry = MemoryEntry(
            layer="L1",
            content=f"[{role}] {content[:500]}",
            topic=topic,
        )
        store.create_memory_entry(entry)
    except Exception:
        pass


def _record_study(topic: str, user_input: str) -> None:
    """Record study activity in user graph."""
    try:
        from codex_mentis.memory.user_graph import UserGraph
        from codex_mentis.cli.commands.onboard import load_profile
        profile = load_profile()
        if profile:
            ug = UserGraph()
            ug.record_study(profile.get("name", "default"), topic, duration_minutes=1)
    except Exception:
        pass


def _check_due_reviews() -> Optional[str]:
    """Check if there are cards due for spaced repetition review."""
    try:
        from codex_mentis.memory.spaced_repetition import SpacedRepetition
        sr = SpacedRepetition()
        due = sr.get_due_reviews()
        if due and len(due) > 0:
            return f"📚 You have {len(due)} concepts due for review. Run `codex-mentis review start`."
    except Exception:
        pass
    return None


def launch_chat(
    mode: str = "study",
    topic: str = "general",
    system_prompt: Optional[str] = None,
) -> None:
    """Launch the interactive chat REPL with all systems connected."""
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    console = Console()
    config = load_provider_config()
    model = config.get("default_model", "unknown")

    # Build system prompt with context
    if system_prompt is None:
        system_prompt = (
            "You are Codex Mentis, an expert mathematics and physics tutor. "
            "You explain concepts clearly using the Socratic method — ask guiding questions "
            "before giving answers. Use LaTeX notation for equations ($..$ inline, $$...$$ display). "
            "Be precise, rigorous, and encouraging. When a student makes a mistake, "
            "guide them to discover the error rather than just correcting it. "
            "Use markdown formatting for structure."
        )

    # Inject user context into system prompt
    user_ctx = _get_user_context()
    if user_ctx:
        system_prompt += f"\n\n{user_ctx}"

    messages = [{"role": "system", "content": system_prompt}]

    # Welcome
    console.print(Panel(
        f"[bold cyan]Codex Mentis[/bold cyan] — {mode.title()} mode\n"
        f"Model: [dim]{model}[/dim] | Topic: [dim]{topic}[/dim]\n\n"
        f"Commands: [cyan]/mode[/cyan] [cyan]/topic[/cyan] [cyan]/model[/cyan] "
        f"[cyan]/verify[/cyan] [cyan]/research[/cyan] [cyan]/clear[/cyan] [cyan]/quit[/cyan]",
        title="🧠 Codex Mentis",
        border_style="blue",
    ))

    # Check for due reviews
    review_msg = _check_due_reviews()
    if review_msg:
        console.print(f"[dim]{review_msg}[/dim]")

    while True:
        try:
            user_input = console.input(f"[bold green]({mode}:{topic}) 🧠 [/bold green]")
            
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
                        console.print(f"[dim]Mode: {mode}[/dim]")
                    continue
                elif cmd == "/topic":
                    if arg:
                        topic = arg.strip()
                        console.print(f"[dim]Topic: {topic}[/dim]")
                    continue
                elif cmd == "/model":
                    if arg:
                        config["default_model"] = arg.strip()
                        model = arg.strip()
                        console.print(f"[dim]Model: {model}[/dim]")
                    continue
                elif cmd == "/verify":
                    if arg:
                        with console.status("[cyan]Verifying...[/cyan]"):
                            from codex_mentis.math_engine.sandbox import SymPySandbox
                            sandbox = SymPySandbox()
                            result = sandbox.evaluate(arg)
                        if result.verified:
                            console.print(f"[green]✓ {result.value}[/green]")
                            if result.latex:
                                console.print(f"  LaTeX: {result.latex}")
                        else:
                            console.print(f"[red]✗ {result.error}[/red]")
                    continue
                elif cmd == "/research":
                    if arg:
                        with console.status("[cyan]Researching...[/cyan]"):
                            from codex_mentis.knowledge.acquisition import KnowledgeAcquisition
                            acquirer = KnowledgeAcquisition()
                            result = acquirer.research_topic(arg, depth="shallow")
                        if result.get("findings"):
                            console.print(f"[bold]Found {len(result['findings'])} findings:[/bold]")
                            for f in result["findings"][:5]:
                                console.print(f"  • {f}")
                    continue
                elif cmd == "/save":
                    from codex_mentis.sessions import save_session
                    sid = save_session(messages, topic=topic, mode=mode)
                    console.print(f"[green]✓ Session saved: {sid}[/green]")
                    continue
                elif cmd == "/sessions":
                    from codex_mentis.sessions import list_sessions
                    sessions = list_sessions()
                    if not sessions:
                        console.print("[dim]No saved sessions.[/dim]")
                    else:
                        for s in sessions:
                            console.print(f"  [cyan]{s['id']}[/cyan] — {s['topic']} ({s['mode']}) — {s['message_count']} msgs")
                    continue
                elif cmd == "/resume":
                    from codex_mentis.sessions import load_session, list_sessions
                    if arg:
                        sid = arg.strip()
                    else:
                        sessions = list_sessions(limit=1)
                        sid = sessions[0]["id"] if sessions else None
                    if sid:
                        loaded = load_session(sid)
                        if loaded:
                            messages = loaded
                            console.print(f"[green]✓ Resumed session {sid} ({len(messages)} messages)[/green]")
                        else:
                            console.print(f"[red]Session not found: {sid}[/red]")
                    else:
                        console.print("[dim]No sessions to resume.[/dim]")
                    continue
                elif cmd == "/quiz":
                    quiz_prompt = (
                        f"Generate a practice problem on '{topic}' at intermediate level. "
                        f"Format: state the problem clearly, then say HINTS: followed by hints. "
                        f"Do NOT give the solution."
                    )
                    messages.append({"role": "user", "content": quiz_prompt})
                    with console.status("[cyan]Generating quiz...[/cyan]"):
                        response = chat_completion(messages, model=model, config=config)
                    messages.append({"role": "assistant", "content": response})
                    console.print()
                    console.print(Markdown(response))
                    console.print()
                    continue
                elif cmd == "/progress":
                    try:
                        from codex_mentis.concepts.graph import ConceptGraph
                        from codex_mentis.memory.user_graph import UserGraph
                        from codex_mentis.cli.commands.onboard import load_profile
                        
                        profile = load_profile()
                        cg = ConceptGraph()
                        ug = UserGraph()
                        
                        console.print(f"[bold]📊 Progress Dashboard[/bold]\n")
                        
                        if profile:
                            console.print(f"Level: {', '.join(f'{k}: {v}' for k, v in profile.get('levels', {}).items())}")
                        
                        console.print(f"Concepts in graph: {len(cg.graph)}")
                        
                        stats = ug.get_user_stats(profile.get("name", "default") if profile else "default")
                        console.print(f"Topics studied: {stats['topics_studied']}")
                        console.print(f"Concepts mastered: {stats['concepts_mastered']}")
                        console.print(f"Total study time: {stats['total_hours']}h")
                        
                        # Knowledge gaps
                        gaps = ug.get_knowledge_gaps(profile.get("name", "default") if profile else "default")
                        if gaps:
                            console.print(f"\n[yellow]Knowledge gaps ({len(gaps)}):[/yellow]")
                            for g in gaps[:5]:
                                console.print(f"  • {g['concept']} (needed for: {g['needed_for']})")
                    except Exception as e:
                        console.print(f"[dim]Progress unavailable: {e}[/dim]")
                    continue
                elif cmd == "/ingest":
                    if arg:
                        from codex_mentis.knowledge.base import KnowledgeBase
                        from codex_mentis.knowledge.ingester import DocumentIngester
                        from codex_mentis.knowledge.chunker import SmartChunker
                        from pathlib import Path
                        
                        target = Path(arg.strip()).expanduser()
                        if target.exists():
                            kb = KnowledgeBase()
                            ingester = DocumentIngester()
                            chunker = SmartChunker()
                            
                            files = list(target.glob("**/*")) if target.is_dir() else [target]
                            exts = {".pdf", ".md", ".txt", ".tex", ".ipynb", ".html"}
                            files = [f for f in files if f.suffix.lower() in exts]
                            
                            count = 0
                            for f in files[:10]:  # Limit to 10 files
                                try:
                                    text = ingester.extract_text(str(f))
                                    if text and len(text) > 50:
                                        chunks = chunker.chunk_text(text, source=str(f))
                                        kb.add_document(str(f), f.stem, topic, chunks=chunks)
                                        count += 1
                                except Exception:
                                    continue
                            console.print(f"[green]✓ Ingested {count}/{len(files)} documents[/green]")
                        else:
                            console.print(f"[red]Path not found: {target}[/red]")
                    else:
                        console.print("[dim]Usage: /ingest <path>[/dim]")
                    continue
                elif cmd == "/latex":
                    if arg:
                        from codex_mentis.latex_render import latex_to_unicode, render_equation_box
                        console.print(render_equation_box(arg))
                    continue
                elif cmd == "/help":
                    console.print(Panel(
                        "[bold]Chat Commands:[/bold]\n"
                        "  /mode <mode>      Switch mode (study/explore/reason/verify)\n"
                        "  /topic <name>     Change topic\n"
                        "  /model <name>     Change model\n"
                        "  /verify <expr>    Verify math with SymPy\n"
                        "  /latex <expr>     Render LaTeX as Unicode\n"
                        "  /quiz             Generate a practice problem\n"
                        "  /progress         Show learning progress dashboard\n"
                        "  /research <q>     Web research\n"
                        "  /ingest <path>    Ingest documents into knowledge base\n"
                        "  /save             Save current session\n"
                        "  /sessions         List saved sessions\n"
                        "  /resume [id]      Resume a saved session\n"
                        "  /clear            Clear conversation\n"
                        "  /quit             Exit\n\n"
                        "[bold]CLI Commands:[/bold]\n"
                        "  codex-mentis setup      Configure providers\n"
                        "  codex-mentis onboard     Set up learning profile\n"
                        "  codex-mentis doctor      System health check\n"
                        "  codex-mentis review      Spaced repetition\n"
                        "  codex-mentis profile     View knowledge map\n",
                        title="Help",
                        border_style="cyan",
                    ))
                    continue
                else:
                    console.print(f"[dim]Unknown: {cmd}. /help for commands.[/dim]")
                    continue

            # ─── MAIN CHAT FLOW ───
            
            # 1. RAG: Retrieve relevant context from knowledge base
            rag_ctx = _get_rag_context(user_input)
            concept_ctx = _get_concept_context(topic)
            
            # 2. Build enriched prompt
            enriched = user_input
            if rag_ctx or concept_ctx:
                context_parts = []
                if rag_ctx:
                    context_parts.append(rag_ctx)
                if concept_ctx:
                    context_parts.append(concept_ctx)
                enriched = "\n\n".join(context_parts) + f"\n\nUser question: {user_input}"

            messages.append({"role": "user", "content": enriched})

            # 3. Get response
            with console.status("[bold cyan]Thinking...[/bold cyan]"):
                response = chat_completion(messages, model=model, config=config)

            messages.append({"role": "assistant", "content": response})

            # 4. Display response
            console.print()
            console.print(Markdown(response))

            # 5. SymPy verification of equations in response
            verification = _verify_math(response)
            if verification:
                console.print(f"\n[dim]{verification}[/dim]")

            # 6. Save to memory
            _save_to_memory("user", user_input, topic=topic)
            _save_to_memory("assistant", response, topic=topic)

            # 7. Record study activity
            _record_study(topic, user_input)

            console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Use /quit to exit.[/dim]")
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break
