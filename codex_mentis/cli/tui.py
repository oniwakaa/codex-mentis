import asyncio
import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Input, Button, Select, TabbedContent, TabPane, Label, Markdown
from textual.reactive import reactive
from textual.worker import get_current_worker, Worker

from codex_mentis.core.config import load_config, CONFIG_DIR
from codex_mentis.cli.widgets.concept_graph import ConceptGraphWidget, ConceptSelected
from codex_mentis.cli.widgets.equation_display import EquationDisplay
from codex_mentis.cli.widgets.split_reasoning import SplitReasoning
from codex_mentis.cli.widgets.proof_tree import ProofTreeWidget
from codex_mentis.cli.widgets.plot_widget import PlotWidget
from codex_mentis.cli.widgets.agent_panel import AgentPanel
from codex_mentis.cli.widgets.memory_viewer import MemoryViewer

from codex_mentis.agents.providers import ProviderConfig, get_provider
from codex_mentis.agents import TutorAgent, ResearchAgent, ProverAgent, ReviewerAgent, VisualizerAgent
from codex_mentis.agents.explainer import ExplainerAgent
from codex_mentis.agents.self_improver import SelfImproverAgent
from codex_mentis.agents.orchestrator import Orchestrator, OrchestratorResponse, AgentResponse

class TuiApp(App):
    """
    Main Codex Mentis Textual TUI application.
    Features a split-screen layout with interactive widgets and real-time streaming agent dialogue.
    """
    
    DEFAULT_CSS = """
    TuiApp {
        background: $background;
        color: $text;
        font-size: 100%;
    }
    
    #top-bar {
        height: 3;
        background: $panel;
        layout: horizontal;
        align: left middle;
        padding-left: 2;
        border-bottom: solid $accent;
    }
    
    #top-bar Label {
        margin-right: 1;
        content-align: center center;
    }
    
    #top-bar Select {
        width: 20;
        margin-right: 3;
    }
    
    #top-bar Input {
        width: 40;
    }
    
    #main-container {
        layout: horizontal;
        width: 100%;
        height: 1fr;
    }
    
    #left-pane {
        width: 40%;
        height: 100%;
        border-right: tall $accent;
        layout: vertical;
    }
    
    #chat-log {
        height: 1fr;
        scrollbar-gutter: stable;
        padding: 1 2;
        overflow-y: scroll;
        layout: vertical;
    }
    
    .chat-bubble {
        margin: 1 0;
        padding: 1 2;
        border-radius: 4;
        width: auto;
        max-width: 90%;
    }
    
    .user-bubble {
        background: $boost;
        border: solid $primary;
        align-self: flex-end;
    }
    
    .assistant-bubble {
        background: $panel;
        border: solid $accent;
        align-self: flex-start;
    }
    
    #chat-input-bar {
        height: 3;
        layout: horizontal;
        border-top: solid $accent;
        background: $boost;
    }
    
    #chat-input-bar Input {
        width: 1fr;
    }
    
    #chat-input-bar Button {
        width: 10;
    }
    
    #right-pane {
        width: 60%;
        height: 100%;
    }
    
    #bottom-bar {
        height: 1;
        background: $primary-darken-3;
        color: white;
        layout: horizontal;
        padding: 0 2;
    }
    
    .status-item {
        margin-right: 4;
    }
    """

    BINDINGS = [
        ("f1", "switch_mode('STUDY')", "Study Mode"),
        ("f2", "switch_mode('EXPLORE')", "Explore Mode"),
        ("f3", "switch_mode('REASON')", "Reason Mode"),
        ("f4", "switch_mode('VERIFY')", "Verify Mode"),
        ("f5", "switch_mode('VISUALIZE')", "Visualize Mode"),
        ("ctrl+t", "toggle_theme", "Toggle Theme"),
        ("ctrl+q", "exit_app", "Quit"),
    ]

    def __init__(self, mode: str = "STUDY", topic: str = "general", **kwargs):
        super().__init__(**kwargs)
        self.initial_mode = mode.upper()
        self.initial_topic = topic
        self.orchestrator: Optional[Orchestrator] = None
        self.provider_name = "gemini"
        
        # Configure and bootstrap orchestrator
        self.initialize_orchestrator()

    def initialize_orchestrator(self) -> None:
        """Loads configuration and builds the orchestrator agent pipeline."""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "mock"
        
        # Default model settings
        self.provider_name = "gemini"
        default_model = "gemini-1.5-flash"
        
        try:
            config_obj = load_config()
            self.provider_name = config_obj.providers.default
            if self.provider_name == "openai":
                default_model = "gpt-4o"
            elif self.provider_name == "anthropic":
                default_model = "claude-3-5-sonnet-20240620"
            elif self.provider_name == "local":
                default_model = "local-model"
        except Exception:
            pass
            
        config = ProviderConfig(
            api_key=api_key,
            model=default_model,
            max_tokens=4096
        )
        
        prov = get_provider(self.provider_name, config)
        
        # Build core agents
        agents = {
            "tutor": TutorAgent(prov),
            "researcher": ResearchAgent(prov),
            "prover": ProverAgent(prov),
            "reviewer": ReviewerAgent(prov),
            "visualizer": VisualizerAgent(prov),
            "explainer": ExplainerAgent(prov),
            "self_improver": SelfImproverAgent(prov)
        }
        
        from codex_mentis.concepts.graph import ConceptGraph
        from codex_mentis.memory.store import MemoryStore
        from codex_mentis.memory.layers import ThreeLayerMemory
        
        # Build support infrastructure
        try:
            concept_graph = ConceptGraph()
            db_store = MemoryStore(db_path=str(CONFIG_DIR / "memory.db"))
            memory_store = ThreeLayerMemory(db_store, prov)
        except Exception:
            concept_graph = None
            memory_store = None
            
        self.orchestrator = Orchestrator(
            agents=agents,
            memory=memory_store,
            concept_graph=concept_graph
        )

    def compose(self) -> ComposeResult:
        yield Header()
        
        # Top panel modes and topics
        mode_options = [
            ("Tutoring/Study", "STUDY"),
            ("Research/Explore", "EXPLORE"),
            ("Proof Derivation", "REASON"),
            ("Logical Verification", "VERIFY"),
            ("Mathematical Plotting", "VISUALIZE")
        ]
        
        yield Horizontal(
            Label("Mode:"),
            Select(mode_options, value=self.initial_mode, id="mode-select"),
            Label("Topic:"),
            Input(value=self.initial_topic, placeholder="Enter math/physics topic...", id="topic-input"),
            id="top-bar"
        )
        
        # Main splitscreen
        yield Horizontal(
            Vertical(
                # Chat History Logs
                Vertical(id="chat-log"),
                # Message input bar
                Horizontal(
                    Input(placeholder="Ask a question or enter a /command...", id="chat-input"),
                    Button("Send", variant="primary", id="send-btn"),
                    id="chat-input-bar"
                ),
                id="left-pane"
            ),
            Vertical(
                TabbedContent(
                    TabPane("Concept Graph", ConceptGraphWidget(id="tui-concept-graph")),
                    TabPane("Split Reasoning", SplitReasoning(id="tui-split-reasoning")),
                    TabPane("Proof Tree", ProofTreeWidget(id="tui-proof-tree")),
                    TabPane("Equation Display", EquationDisplay(latex_str="\\mathcal{L} = T - V", title="Lagrangian", id="tui-equation-display")),
                    TabPane("Plot", PlotWidget(expr="x**2", id="tui-plot")),
                    TabPane("Memory Viewer", MemoryViewer(id="tui-memory-viewer")),
                    TabPane("Agent Monitor", AgentPanel(id="tui-agent-panel")),
                    id="tabs"
                ),
                id="right-pane"
            ),
            id="main-container"
        )
        
        # Bottom status indicators
        yield Horizontal(
            Label("Status: Idle", id="status-agent", classes="status-item"),
            Label("Confidence: 100%", id="status-confidence", classes="status-item"),
            Label("Tools: None", id="status-tools", classes="status-item"),
            Label(f"Provider: {self.provider_name.upper()}", id="status-provider", classes="status-item"),
            Label("Memory: Clean", id="status-memory", classes="status-item"),
            Label("Theme: Dark", id="status-theme", classes="status-item"),
            id="bottom-bar"
        )
        
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Codex Mentis CLI"
        self.sub_title = "Dynamic Math & Physics Agent TUI"
        
        # Add welcome greeting in chat log
        chat_log = self.query_one("#chat-log", Vertical)
        welcome_md = (
            f"### Welcome to **Codex Mentis**!\n\n"
            f"Collaborative AI agents are ready to assist you. Mode is set to **{self.initial_mode}** for topic **{self.initial_topic}**.\n\n"
            f"- Try typing a formula, or ask a tutor guidance question.\n"
            f"- Type `/help` to see all available slash commands.\n"
            f"- Use shortcuts `F1`-`F5` to switch modes, or click tabs to explore visualizers."
        )
        chat_log.mount(Markdown(welcome_md, classes="chat-bubble assistant-bubble"))
        self.update_memory_status()

    def update_memory_status(self) -> None:
        """Check L1/L2/L3 entry counts to display in status bar."""
        try:
            conn = sqlite3.connect(CONFIG_DIR / "memory.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memory_entries")
            cnt = cursor.fetchone()[0]
            conn.close()
            self.query_one("#status-memory", Label).update(f"Memory entries: {cnt}")
        except Exception:
            self.query_one("#status-memory", Label).update("Memory: Unavailable")

    def action_switch_mode(self, mode: str) -> None:
        """Keyboard action shortcut to switch agent study mode."""
        self.query_one("#mode-select", Select).value = mode
        self.add_system_message(f"Switched mode to {mode}.")

    def action_toggle_theme(self) -> None:
        """Swap light and dark theme styles."""
        self.theme = "light" if self.theme == "dark" else "dark"
        theme_lbl = self.query_one("#status-theme", Label)
        theme_lbl.update(f"Theme: {self.theme.upper()}")

    def action_exit_app(self) -> None:
        self.exit()

    def add_system_message(self, text: str) -> None:
        chat_log = self.query_one("#chat-log", Vertical)
        chat_log.mount(Static(f"[italic grey50]System: {text}[/italic grey50]", classes="chat-bubble"))
        # Scroll to bottom
        chat_log.scroll_end(animate=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input":
            self.process_chat_input()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            self.process_chat_input()

    def process_chat_input(self) -> None:
        chat_input = self.query_one("#chat-input", Input)
        user_text = chat_input.value.strip()
        if not user_text:
            return
            
        chat_input.value = ""
        
        # Print user message to chat log
        chat_log = self.query_one("#chat-log", Vertical)
        chat_log.mount(Markdown(f"**You:** {user_text}", classes="chat-bubble user-bubble"))
        chat_log.scroll_end(animate=False)
        
        # Intercept slash commands
        if user_text.startswith("/"):
            self.execute_slash_command(user_text)
            return
            
        # Get mode and topic settings
        mode = str(self.query_one("#mode-select", Select).value or "STUDY").lower()
        topic = self.query_one("#topic-input", Input).value.strip() or "general"
        
        # Reset agent panels status monitor
        self.query_one("#tui-agent-panel", AgentPanel).set_all_idle()
        
        # Run async agent orchestrator query in background worker
        self.run_worker(self.execute_orchestration(user_text, mode, topic), exclusive=True)

    def execute_slash_command(self, command_str: str) -> None:
        """Parses and executes slash commands in the TUI app."""
        parts = command_str.split(" ", 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        chat_log = self.query_one("#chat-log", Vertical)
        tabs = self.query_one("#tabs", TabbedContent)
        
        if cmd in ("/quit", "/exit"):
            self.exit()
            
        elif cmd == "/clear":
            for child in list(chat_log.children):
                child.remove()
            self.add_system_message("Chat history cleared.")
            
        elif cmd == "/help":
            help_md = (
                "#### Available Slash Commands:\n"
                "- `/mode <MODE> <topic>` - Switch mode (STUDY/EXPLORE/REASON) and topic\n"
                "- `/plot <expression>` - Plot function & open Plot tab\n"
                "- `/concept map` - Open concept DAG graph visualizer\n"
                "- `/memory show` - Open memory auditor layers viewer\n"
                "- `/verify <claim>` - Run SymPy verification check\n"
                "- `/clear` - Clear chat history logs\n"
                "- `/help` - Show this dialogue manual\n"
                "- `/quit` or `/exit` - Exit app"
            )
            chat_log.mount(Markdown(help_md, classes="chat-bubble assistant-bubble"))
            chat_log.scroll_end(animate=False)
            
        elif cmd == "/mode":
            mode_parts = arg.split(" ", 1)
            new_mode = mode_parts[0].upper()
            new_topic = mode_parts[1] if len(mode_parts) > 1 else "general"
            if new_mode not in ("STUDY", "EXPLORE", "REASON", "VERIFY", "VISUALIZE"):
                self.add_system_message(f"Unknown mode: {new_mode}. Use STUDY, EXPLORE, REASON, VERIFY, or VISUALIZE.")
            else:
                self.query_one("#mode-select", Select).value = new_mode
                self.query_one("#topic-input", Input).value = new_topic
                self.add_system_message(f"Switched mode to {new_mode} for topic: {new_topic}")
                
        elif cmd == "/plot":
            if not arg:
                self.add_system_message("Usage: /plot <expression> (e.g. sin(x))")
            else:
                plot_widget = self.query_one("#tui-plot", PlotWidget)
                plot_widget.set_expression(arg)
                tabs.active = "tab-5"  # Tab index for Plot
                self.add_system_message(f"Plotting function: {arg}")
                
        elif cmd == "/concept":
            tabs.active = "tab-1"  # Concept Graph
            self.add_system_message("Opened Concept Graph.")
            
        elif cmd == "/memory":
            tabs.active = "tab-6"  # Memory Viewer
            self.add_system_message("Opened Memory Layers Auditor.")
            
        elif cmd == "/verify":
            if not arg:
                self.add_system_message("Usage: /verify <claim> (e.g. sin(x)**2 + cos(x)**2 = 1)")
            else:
                self.add_system_message(f"Verifying claim: {arg}")
                self.run_worker(self.execute_orchestration(f"Verify claim: {arg}", "verify", "general"), exclusive=True)
                
        else:
            self.add_system_message(f"Unknown slash command: {cmd}")

    async def execute_orchestration(self, query: str, mode: str, topic: str) -> None:
        """Asynchronous background worker task that streams response token-by-token."""
        chat_log = self.query_one("#chat-log", Vertical)
        status_lbl = self.query_one("#status-agent", Label)
        conf_lbl = self.query_one("#status-confidence", Label)
        tools_lbl = self.query_one("#status-tools", Label)
        agent_panel = self.query_one("#tui-agent-panel", AgentPanel)
        
        # 1. Update UI Status: Active Agent Thinking
        active_agent = "Tutor"
        if mode == "explore":
            active_agent = "Researcher"
        elif mode == "reason":
            active_agent = "Prover"
        elif mode == "verify":
            active_agent = "Reviewer"
        elif mode == "visualize":
            active_agent = "Visualizer"
            
        status_lbl.update(f"Status: {active_agent} (Thinking...)")
        agent_panel.update_agent(active_agent, "Thinking", thoughts="Formulating response...")
        
        # 2. Add empty streaming block to chat log
        bubble = Markdown("", classes="chat-bubble assistant-bubble")
        chat_log.mount(bubble)
        chat_log.scroll_end(animate=False)
        
        # Find active agent based on mode
        agent_key = None
        if "study" in mode:
            agent_key = "tutor"
        elif "explore" in mode:
            agent_key = "researcher"
        elif mode in ("derive", "reason", "prover"):
            agent_key = "prover"
        elif "verify" in mode or "review" in mode:
            agent_key = "reviewer"
        elif mode in ("plot", "visualize", "visualizer"):
            agent_key = "visualizer"
            
        agent = self.orchestrator.agents.get(agent_key)
        if not agent:
            # Fallback
            agent = list(self.orchestrator.agents.values())[0] if self.orchestrator.agents else None
            
        if not agent or self.orchestrator is None:
            bubble.update("Error: No active agent or orchestrator initialized.")
            status_lbl.update("Status: Idle")
            return

        # Build prompt messages
        context_str = f"Topic: {topic}"
        messages = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": f"--- CONTEXT ---\n{context_str}\n---------------\n\n{query}"}
        ]
        
        full_response = ""
        
        # 3. Stream tokens
        try:
            agent_panel.update_agent(active_agent, "Working", thoughts="Streaming token output...")
            tools_lbl.update(f"Tools: {', '.join([t['function']['name'] for t in agent.tools]) if agent.tools else 'None'}")
            
            async for token in agent.provider.astream(messages):
                # Ensure worker hasn't been cancelled/replaced
                if get_current_worker().is_cancelled:
                    return
                full_response += token
                bubble.update(full_response)
                # Keep scroll down
                chat_log.scroll_end(animate=False)
                await asyncio.sleep(0.01) # Yield execution for UI loop responsiveness
                
            # If successful, calculate confidence heuristic from content
            confidence = 1.0
            import re
            conf_match = re.search(r"<confidence>\s*(0\.\d+|1\.0|1)\s*</confidence>", full_response, re.IGNORECASE)
            if conf_match:
                confidence = float(conf_match.group(1))
            elif any(w in full_response.lower() for w in ["unsure", "maybe", "not certain"]):
                confidence = 0.7
                
            conf_lbl.update(f"Confidence: {confidence * 100:.0f}%")
            agent_panel.update_agent(active_agent, "Idle", confidence=confidence, thoughts="Idle. Final response delivered.")
            
        except Exception as e:
            full_response += f"\n\n*Error during streaming: {str(e)}*"
            bubble.update(full_response)
            agent_panel.update_agent(active_agent, "Error", thoughts=f"Execution failed: {str(e)}")
            
        status_lbl.update("Status: Idle")
        self.update_memory_status()
        
        # Save dialogue to L1 memory database
        if self.orchestrator.memory:
            try:
                self.orchestrator.memory.add_message({"role": "user", "content": query})
                self.orchestrator.memory.add_message({"role": "assistant", "content": full_response})
            except Exception:
                pass
                
        # 4. Smart update of visualizer widgets based on response content
        tabs = self.query_one("#tabs", TabbedContent)
        
        # Check LaTeX formulas
        formulas = re.findall(r"\$\$(.*?)\$\$", full_response)
        if not formulas:
            formulas = re.findall(r"\$(.*?)\$", full_response)
        if formulas:
            eq_widget = self.query_one("#tui-equation-display", EquationDisplay)
            eq_widget.set_equation(formulas[0], title=f"Formula on {topic.title()}")
            tabs.active = "tab-4" # Switch to Equation display
            
        # Check equations to plot
        if "plot" in query.lower() or "visualize" in query.lower():
            plot_expr = None
            for eq in formulas:
                if "=" in eq and "x" in eq:
                    parts = eq.split("=")
                    plot_expr = parts[1].replace("\\sin", "sin").replace("\\cos", "cos").replace("\\exp", "exp").strip()
                    break
            if not plot_expr:
                plot_expr = "x**2"
            plot_widget = self.query_one("#tui-plot", PlotWidget)
            plot_widget.set_expression(plot_expr)
            tabs.active = "tab-5" # Switch to Plot
            
        # Check proof trees/derivations
        if "prove" in query.lower() or "derive" in query.lower() or "proof" in query.lower() or mode == "reason":
            # Populate split reasoning widget
            split_widget = self.query_one("#tui-split-reasoning", SplitReasoning)
            split_widget.split_and_set_text(full_response)
            
            # Populate proof tree step widget
            steps = [line.strip() for line in full_response.splitlines() if line.strip().startswith(("Step", "* Step", "- Step"))]
            if steps:
                tree_widget = self.query_one("#tui-proof-tree", ProofTreeWidget)
                tree_widget.set_proof_steps(steps, title=f"Proof for {topic.title()}")
                tabs.active = "tab-3" # Switch to Proof Tree
            else:
                tabs.active = "tab-2" # Switch to Split Reasoning

    def on_concept_selected(self, event: ConceptSelected) -> None:
        """Triggered when user clicks a concept node in the DAG visualizer."""
        self.query_one("#topic-input", Input).value = event.concept_id
        self.add_system_message(f"Selected concept from graph: {event.concept_name} ({event.concept_id})")
        # Trigger Socratic explanation of that concept
        self.run_worker(self.execute_orchestration(f"Explain the concept of {event.concept_name}.", "study", event.concept_id), exclusive=True)
