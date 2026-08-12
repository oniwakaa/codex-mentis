import os
import re
import asyncio
import sqlite3
from typing import Optional, List, Dict, Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ContentSwitcher
from textual.widgets import Static, Input, Button
from textual.reactive import reactive
from textual.command import Provider, Hit, Hits
from rich.text import Text
from rich.markdown import Markdown

from codex_mentis.cli.widgets import (
    ConceptGraphWidget,
    SplitReasoningPanel,
    ProofTreeWidget,
    PlotWidget,
    AgentPanel,
    MemoryViewer,
)
from codex_mentis.core.config import load_config

class CodexCommandProvider(Provider):
    """Fuzzy-search command palette provider for Codex Mentis."""
    
    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        
        # Define available commands
        commands = [
            ("Switch to Study Mode", lambda: self.app.switch_mode_action("STUDY"), "F1 - View concept DAG"),
            ("Switch to Explore Mode", lambda: self.app.switch_mode_action("EXPLORE"), "F2 - Learn new domains"),
            ("Switch to Reason Mode", lambda: self.app.switch_mode_action("REASON"), "F3 - Step-by-step derivation"),
            ("Switch to Verify Mode", lambda: self.app.switch_mode_action("VERIFY"), "F4/Ctrl+V - Audit claims"),
            ("Switch to Visualize Mode", lambda: self.app.switch_mode_action("VISUALIZE"), "F5 - Mathematical plots"),
            ("Switch to Research Mode", lambda: self.app.switch_mode_action("RESEARCH"), "Ctrl+R - Literature search"),
            ("Clear Conversation Log", self.app.clear_chat, "Resets conversation logs"),
            ("Reset Tool Logs", self.app.clear_tool_logs, "Resets operations panel logs"),
        ]
        
        for name, callback, desc in commands:
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(name),
                    callback=callback,
                    help=desc
                )

class CodexMentisTUI(App):
    """The central Textual TUI Application for Codex Mentis."""
    
    TITLE = "Codex Mentis math & physics IDE"
    COMMANDS = App.COMMANDS | {CodexCommandProvider}
    
    DEFAULT_CSS = """
    Screen {
        background: #0f172a;
        color: #cbd5e1;
    }
    #top_bar {
        height: 3;
        background: #1e293b;
        border-bottom: solid #334155;
        padding: 0 1;
        layout: horizontal;
    }
    #mode_selectors {
        width: 65fr;
        height: 3;
        layout: horizontal;
        align-vertical: middle;
    }
    #topic_input_container {
        width: 35fr;
        height: 3;
        layout: horizontal;
        align-vertical: middle;
        align-horizontal: right;
    }
    #topic_label {
        color: #94a3b8;
        margin-top: 1;
        margin-right: 1;
        text-style: bold;
    }
    #topic_input {
        width: 25;
        height: 1;
    }
    #main_split {
        height: 1fr;
        width: 100%;
        layout: horizontal;
    }
    #left_panel {
        width: 45fr;
        height: 1fr;
        border-right: solid #334155;
        layout: vertical;
    }
    #chat_history {
        height: 1fr;
        overflow-y: scroll;
        padding: 1 2;
        layout: vertical;
    }
    .user-msg {
        margin-top: 1;
        margin-bottom: 1;
        padding: 1;
        background: #1e293b;
        border-left: solid #22c55e 3;
    }
    .agent-msg {
        margin-top: 1;
        margin-bottom: 1;
        padding: 1;
        background: #0f172a;
    }
    .system-msg {
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        color: #94a3b8;
        text-style: italic;
    }
    #input_container {
        height: 4;
        padding: 1;
        background: #1e293b;
        border-top: solid #334155;
    }
    #chat_input {
        width: 100%;
        height: 1;
    }
    #right_panel {
        width: 55fr;
        height: 1fr;
        layout: vertical;
    }
    #right_switcher {
        height: 3fr;
        width: 100%;
    }
    #operation_panel_container {
        height: 1fr;
        width: 100%;
        border-top: solid #334155;
    }
    #bottom_bar {
        height: 1;
        background: #0284c7;
        color: #ffffff;
        padding: 0 2;
        text-style: bold;
    }
    Button {
        background: #334155;
        color: #cbd5e1;
        border: none;
        height: 1;
        margin-right: 1;
        min-width: 11;
        padding: 0 1;
    }
    Button:hover {
        background: #475569;
    }
    Button.active-mode {
        background: #0284c7;
        color: #ffffff;
        text-style: bold;
    }
    """

    BINDINGS = [
        ("f1", "switch_mode_study", "Study Mode"),
        ("f2", "switch_mode_explore", "Explore Mode"),
        ("f3", "switch_mode_reason", "Reason Mode"),
        ("f4", "switch_mode_verify", "Verify Mode"),
        ("f5", "switch_mode_visualize", "Visualize Mode"),
        ("ctrl+r", "switch_mode_research", "Research Mode"),
        ("ctrl+v", "switch_mode_verify", "Verify Mode"),
        ("ctrl+p", "command_palette", "Commands"),
    ]

    active_mode = reactive("STUDY")
    active_topic = reactive("general")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize dependencies
        from codex_mentis.concepts.graph import ConceptGraph
        from codex_mentis.concepts.tracker import MasteryTracker
        from codex_mentis.memory.store import MemoryStore
        
        self.concept_graph = ConceptGraph()
        self.mastery_tracker = MasteryTracker(concept_graph=self.concept_graph)
        self.memory_store = MemoryStore()
        
        # Load active provider details
        self.config_obj = load_config()
        self.default_provider_name = self.config_obj.providers.default
        
        # Socratic fallback default initialization (will load full orchestrator if available)
        self.orchestrator = None
        self._init_orchestrator()

    def _init_orchestrator(self) -> None:
        """Initializes actual Orchestrator and specialized agents using provider configs."""
        try:
            from codex_mentis.agents.providers import ProviderConfig, get_provider
            from codex_mentis.agents.tutor import TutorAgent
            from codex_mentis.agents.researcher import ResearchAgent
            from codex_mentis.agents.prover import ProverAgent
            from codex_mentis.agents.reviewer import ReviewerAgent
            from codex_mentis.agents.visualizer import VisualizerAgent
            from codex_mentis.agents.explainer import ExplainerAgent
            from codex_mentis.agents.self_improver import SelfImproverAgent
            from codex_mentis.agents.orchestrator import Orchestrator
            
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "mock"
            
            default_model = "gemini-1.5-flash"
            if self.default_provider_name == "openai":
                default_model = "gpt-4o"
            elif self.default_provider_name == "anthropic":
                default_model = "claude-3-5-sonnet-20240620"
            elif self.default_provider_name == "local":
                default_model = "local-model"
                
            prov_config = ProviderConfig(
                api_key=api_key,
                model=default_model,
                max_tokens=4096
            )
            
            provider = get_provider(self.default_provider_name, prov_config)
            
            agents = {
                "tutor": TutorAgent(provider),
                "researcher": ResearchAgent(provider),
                "prover": ProverAgent(provider),
                "reviewer": ReviewerAgent(provider),
                "visualizer": VisualizerAgent(provider),
                "explainer": ExplainerAgent(provider),
                "self_improver": SelfImproverAgent(provider)
            }
            
            self.orchestrator = Orchestrator(
                agents=agents,
                memory=self.memory_store,
                concept_graph=self.concept_graph
            )
        except Exception:
            # Fallback to simulated Socratic mock
            self.orchestrator = None

    def compose(self) -> ComposeResult:
        # Top Bar
        with Horizontal(id="top_bar"):
            with Horizontal(id="mode_selectors"):
                yield Button("Study (F1)", id="btn_study")
                yield Button("Explore (F2)", id="btn_explore")
                yield Button("Reason (F3)", id="btn_reason")
                yield Button("Verify (F4)", id="btn_verify")
                yield Button("Visualize (F5)", id="btn_visualize")
                yield Button("Research (^R)", id="btn_research")
            with Horizontal(id="topic_input_container"):
                yield Static("Topic:", id="topic_label")
                yield Input(value=self.active_topic, placeholder="Current topic...", id="topic_input")
                
        # Main Split Panel
        with Horizontal(id="main_split"):
            # Left panel (chat log)
            with Vertical(id="left_panel"):
                with Vertical(id="chat_history"):
                    yield Static("[bold magenta]Codex Mentis Math & Physics Workspace[/bold magenta]\n"
                                 "Type a query below to prompt the AI agent reasoning loops.\n"
                                 "Press [bold cyan]Ctrl+P[/bold cyan] to open command palette fuzzy search.", classes="system-msg")
                with Container(id="input_container"):
                    yield Input(placeholder="Ask a question or input a derivation query...", id="chat_input")
            
            # Right panel (switching visualizations + operations logger)
            with Vertical(id="right_panel"):
                with ContentSwitcher(initial="concept_graph_view", id="right_switcher"):
                    yield ConceptGraphWidget(
                        concept_graph=self.concept_graph,
                        mastery_tracker=self.mastery_tracker,
                        id="concept_graph_view"
                    )
                    yield SplitReasoningPanel(id="split_reasoning_view")
                    yield ProofTreeWidget(id="proof_tree_view")
                    yield PlotWidget(id="plot_view")
                    yield MemoryViewer(memory_store=self.memory_store, id="memory_view")
                    
                with Container(id="operation_panel_container"):
                    yield AgentPanel(id="operation_panel")
                    
        # Bottom status bar
        yield Static(id="bottom_bar")

    def on_mount(self) -> None:
        self.update_bottom_bar()
        self.switch_mode_action("STUDY")
        
        # Attach graph click callbacks to update active topic
        graph_widget = self.query_one("#concept_graph_view", ConceptGraphWidget)
        graph_widget.set_click_callback(self.on_concept_selected)

    def on_concept_selected(self, concept_name: str) -> None:
        """Triggered when user clicks a node in the interactive concept graph."""
        self.active_topic = concept_name
        self.query_one("#topic_input", Input).value = concept_name
        self.append_system_message(f"Selected concept: [bold cyan]{concept_name}[/bold cyan] for study.")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "topic_input":
            self.active_topic = event.value
            self.update_bottom_bar()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat_input":
            user_text = event.value.strip()
            if not user_text:
                return
            event.input.value = ""
            # Run async agent queries without blocking TUI drawing
            self.run_worker(self.process_agent_query(user_text))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Match button IDs to switch modes
        btn_id = event.button.id
        if btn_id == "btn_study":
            self.switch_mode_action("STUDY")
        elif btn_id == "btn_explore":
            self.switch_mode_action("EXPLORE")
        elif btn_id == "btn_reason":
            self.switch_mode_action("REASON")
        elif btn_id == "btn_verify":
            self.switch_mode_action("VERIFY")
        elif btn_id == "btn_visualize":
            self.switch_mode_action("VISUALIZE")
        elif btn_id == "btn_research":
            self.switch_mode_action("RESEARCH")

    # Bindings action hooks
    def action_switch_mode_study(self) -> None:
        self.switch_mode_action("STUDY")
    def action_switch_mode_explore(self) -> None:
        self.switch_mode_action("EXPLORE")
    def action_switch_mode_reason(self) -> None:
        self.switch_mode_action("REASON")
    def action_switch_mode_verify(self) -> None:
        self.switch_mode_action("VERIFY")
    def action_switch_mode_visualize(self) -> None:
        self.switch_mode_action("VISUALIZE")
    def action_switch_mode_research(self) -> None:
        self.switch_mode_action("RESEARCH")

    def switch_mode_action(self, mode: str) -> None:
        """Central mode-switching logic updates buttons, switcher, and layouts."""
        self.active_mode = mode
        
        # 1. Update mode selector button states
        for m in ["study", "explore", "reason", "verify", "visualize", "research"]:
            btn = self.query_one(f"#btn_{m}", Button)
            if m.upper() == mode:
                btn.add_class("active-mode")
            else:
                btn.remove_class("active-mode")
                
        # 2. Transition content switcher
        switcher = self.query_one("#right_switcher", ContentSwitcher)
        if mode == "STUDY":
            switcher.current = "concept_graph_view"
            self.query_one("#concept_graph_view", ConceptGraphWidget).redraw()
        elif mode == "REASON":
            switcher.current = "split_reasoning_view"
        elif mode == "VERIFY":
            switcher.current = "proof_tree_view"
        elif mode == "VISUALIZE":
            switcher.current = "plot_view"
        elif mode in ("EXPLORE", "RESEARCH"):
            switcher.current = "memory_view"
            self.query_one("#memory_view", MemoryViewer).refresh_all()
            
        self.update_bottom_bar()

    def update_bottom_bar(self) -> None:
        """Refresh stats and configuration labels displayed on the bottom bar."""
        try:
            with sqlite3.connect(self.memory_store.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM memories")
                mem_count = cursor.fetchone()[0]
        except Exception:
            mem_count = 0
            
        footer = self.query_one("#bottom_bar", Static)
        status_text = (
            f" 🧠 MODE: {self.active_mode} | "
            f"📂 TOPIC: {self.active_topic} | "
            f"🔌 PROVIDER: {self.default_provider_name} | "
            f"💾 MEMORY: {mem_count} entries"
        )
        footer.update(status_text)

    def append_system_message(self, text: str) -> None:
        chat_history = self.query_one("#chat_history", Vertical)
        msg = Static(text, classes="system-msg")
        chat_history.mount(msg)
        chat_history.scroll_end(animate=False)

    async def append_agent_message(self, text: str) -> None:
        """Types out agent response typewriter style in real-time, completing with markdown rendering."""
        chat_history = self.query_one("#chat_history", Vertical)
        msg_widget = Static("", classes="agent-msg")
        chat_history.mount(msg_widget)
        chat_history.scroll_end(animate=False)
        
        # Type out characters in chunks to keep rendering fast but interactive
        chunk_size = 5
        current_text = ""
        for i in range(0, len(text), chunk_size):
            current_text += text[i:i+chunk_size]
            msg_widget.update(current_text)
            chat_history.scroll_end(animate=False)
            await asyncio.sleep(0.01)
            
        # Final update using markdown formatting for equations and tables
        msg_widget.update(Markdown(text))
        chat_history.scroll_end(animate=False)

    async def process_agent_query(self, user_text: str) -> None:
        """Executes the agent orchestrator response chain asynchronously."""
        # 1. Display user query
        chat_history = self.query_one("#chat_history", Vertical)
        user_msg = Static(f"[bold green]You:[/bold green] {user_text}", classes="user-msg")
        chat_history.mount(user_msg)
        chat_history.scroll_end(animate=False)
        
        # 2. Show operations thinking logger status
        agent_panel = self.query_one("#operation_panel", AgentPanel)
        agent_panel.active_agent = "Orchestrator"
        agent_panel.current_tool = "aprocess"
        agent_panel.confidence = 0.5
        
        self.append_system_message("Thinking...")
        
        # 3. Call agent processes
        try:
            if self.orchestrator:
                response = await self.orchestrator.aprocess(
                    user_input=user_text,
                    mode=self.active_mode.lower(),
                    context=f"Topic: {self.active_topic}"
                )
                response_content = response.content
                routed_agent = response.metadata.get("routed_agent", "tutor")
                workflow = response.metadata.get("workflow", "single-agent")
                agent_responses = response.agent_responses
            else:
                # Socratic mock fallback
                await asyncio.sleep(1.0)
                from codex_mentis.cli.repl import orchestrate
                response_content = orchestrate(
                    query=user_text,
                    mode=self.active_mode,
                    topic=self.active_topic
                )
                routed_agent = "tutor"
                workflow = "socratic-mock"
                agent_responses = []

            # Remove thinking indicators
            thinking_msg = self.query(".system-msg").last()
            if thinking_msg:
                thinking_msg.remove()

            # 4. Process token and operation metadata
            prompt_tokens = 0
            completion_tokens = 0
            for r in agent_responses:
                if hasattr(r, "token_usage") and r.token_usage:
                    prompt_tokens += r.token_usage.get("prompt_tokens", 0)
                    completion_tokens += r.token_usage.get("completion_tokens", 0)
                    
            if prompt_tokens == 0:
                # Mock token increments
                prompt_tokens = len(user_text) // 2
                completion_tokens = len(response_content) // 2

            confidence = 0.95 if self.active_mode in ("VERIFY", "VISUALIZE") else 0.85

            agent_panel.update_status(
                agent=f"{routed_agent.title()} ({workflow})",
                tool="None",
                confidence=confidence,
                prompt_t=prompt_tokens,
                completion_t=completion_tokens
            )

            # Log tool calls in operational panel
            for r in agent_responses:
                if hasattr(r, "metadata") and r.metadata:
                    for k, v in r.metadata.items():
                        agent_panel.log_tool_call(k, str(v)[:30])

            # 5. Output response and sync widgets
            await self.append_agent_message(response_content)
            self.parse_response_and_update_widgets(response_content)
            self.update_bottom_bar()

            # Refresh memory viewer if open
            self.query_one("#memory_view", MemoryViewer).refresh_all()

        except Exception as e:
            thinking_msg = self.query(".system-msg").last()
            if thinking_msg:
                thinking_msg.remove()
            self.append_system_message(f"[bold red]System Error:[/bold red] {e}")
            agent_panel.active_agent = "Idle"
            agent_panel.current_tool = "None"
            agent_panel.confidence = 0.0

    def parse_response_and_update_widgets(self, response_text: str) -> None:
        """Route parts of agent response content to the appropriate specialized widgets."""
        # Update derivation reasoning panel
        split_panel = self.query_one("#split_reasoning_view", SplitReasoningPanel)
        split_panel.parse_and_update(response_text)
        
        # Update proof trees
        proof_tree = self.query_one("#proof_tree_view", ProofTreeWidget)
        proof_tree.parse_and_load(response_text)
        
        # Check for LaTeX plot equations
        plot_widget = self.query_one("#plot_view", PlotWidget)
        equations = re.findall(r"\$\$(.*?)\$\$", response_text)
        if not equations:
            equations = re.findall(r"\$(.*?)\$", response_text)
            
        plot_expr = None
        for eq in equations:
            if "=" in eq and "x" in eq:
                parts = eq.split("=")
                clean_rhs = parts[1].replace("\\sin", "sin").replace("\\cos", "cos").replace("\\exp", "exp").strip()
                plot_expr = clean_rhs
                break
                
        if not plot_expr:
            # Check for explicit plot string matches
            expr_match = re.search(r"plot\s+([a-zA-Z0-9\s\+\-\*\/\(\)\^]+)", response_text, re.IGNORECASE)
            if expr_match:
                plot_expr = expr_match.group(1).strip()
                
        if plot_expr:
            try:
                clean_expr = plot_expr.replace("{", "").replace("}", "")
                plot_widget.add_expression(clean_expr)
            except Exception:
                pass

    def clear_chat(self) -> None:
        """Action callback to purge chat log layout."""
        chat_history = self.query_one("#chat_history", Vertical)
        # Remove all children except the initial welcome system message
        for child in list(chat_history.children)[1:]:
            child.remove()

    def clear_tool_logs(self) -> None:
        """Action callback to clear agent panel logs."""
        agent_panel = self.query_one("#operation_panel", AgentPanel)
        agent_panel.clear_logs()

def launch_tui() -> None:
    app = CodexMentisTUI()
    app.run()

if __name__ == "__main__":
    launch_tui()
