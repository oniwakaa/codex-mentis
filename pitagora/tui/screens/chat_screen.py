"""ChatScreen: full-screen chat view with interactive controller dispatch."""

import time
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input

from pitagora.tui.events import ConceptUpdated, DiagnosticsUpdated, JourneyProgressChanged
from pitagora.tui.widgets import (
    AgentStatusWidget,
    CommandPaletteWidget,
    ConceptTreeWidget,
    InteractivePlotWidget,
    JourneyBarWidget,
    MemoryInspectorWidget,
    MessageLogWidget,
    TokenMeterWidget,
)



class ChatScreen(Screen):
    """Three-column layout for interactive conversation, curriculum tree, and inspector."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            with Vertical(id="sidebar"):
                yield JourneyBarWidget(id="journey-bar")
                yield ConceptTreeWidget(id="concept-tree")
            with Vertical(id="main-panel"):
                yield MessageLogWidget(id="message-log")
                yield Input(
                    placeholder="Ask a math/physics question or type / for commands...",
                    id="chat-input",
                )
                yield CommandPaletteWidget(id="command-palette")
            with Vertical(id="inspector"):
                yield AgentStatusWidget(id="agent-status")
                yield InteractivePlotWidget(id="interactive-plot")
                yield TokenMeterWidget(id="token-meter")
                yield MemoryInspectorWidget(id="memory-inspector")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#chat-input").focus()
        self._sync_runtime_info()

    def _sync_runtime_info(self) -> None:
        app = self.app
        controller = getattr(app, "controller", None)
        if not controller:
            return
        status_w = self.query_one("#agent-status", AgentStatusWidget)
        model = getattr(controller, "model", "gpt-4o")
        status_w.model = str(model)
        if "claude" in str(model).lower():
            status_w.provider = "Anthropic"
        elif "ollama" in str(model).lower() or "local" in str(model).lower():
            status_w.provider = "Local (Ollama)"
        else:
            status_w.provider = "OpenAI"

        journey_w = self.query_one("#journey-bar", JourneyBarWidget)
        journey_w.topic = str(getattr(controller, "topic", "General")).title()

    def on_input_changed(self, event: Input.Changed) -> None:
        palette = self.query_one("#command-palette", CommandPaletteWidget)
        if event.value.startswith("/"):
            palette.command_query = event.value
            palette.styles.display = "block"
        else:
            palette.styles.display = "none"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        palette = self.query_one("#command-palette", CommandPaletteWidget)
        palette.styles.display = "none"
        self.process_user_input(text)

    def scroll_log_up(self) -> None:
        self.query_one("#message-log", MessageLogWidget).scroll_up_lines(3)

    def scroll_log_down(self) -> None:
        self.query_one("#message-log", MessageLogWidget).scroll_down_lines(3)

    def page_log_up(self) -> None:
        self.query_one("#message-log", MessageLogWidget).page_up()

    def page_log_down(self) -> None:
        self.query_one("#message-log", MessageLogWidget).page_down()

    @work(exclusive=True, thread=True)
    def process_user_input(self, text: str) -> None:
        app = self.app
        controller = getattr(app, "controller", None)
        if not controller:
            return

        msg_log = self.query_one("#message-log", MessageLogWidget)
        status_widget = self.query_one("#agent-status", AgentStatusWidget)
        meter_widget = self.query_one("#token-meter", TokenMeterWidget)
        journey_widget = self.query_one("#journey-bar", JourneyBarWidget)
        tree_widget = self.query_one("#concept-tree", ConceptTreeWidget)
        memory_widget = self.query_one("#memory-inspector", MemoryInspectorWidget)

        start_time = time.time()
        status_widget.tool_status = "running"

        for event in controller.handle_input(text):
            elapsed = time.time() - start_time
            status_widget.latency_s = elapsed

            if event.kind == "user":
                msg_log.messages = list(msg_log.messages) + [
                    {"role": "user", "content": str(event.content)}
                ]
            elif event.kind in ("markdown", "text", "renderable"):
                content_str = str(event.content)
                msg_log.messages = list(msg_log.messages) + [
                    {"role": "assistant", "content": content_str}
                ]
                # Estimate token velocity
                approx_tokens = max(1, len(content_str.split()) * 4 // 3)
                if elapsed > 0.05:
                    tps = approx_tokens / elapsed
                    meter_widget.tokens_per_sec = tps
                    status_widget.velocity_tps = tps
                status_widget.tool_status = "success"

            elif event.kind == "plot":
                plot_data = event.content if isinstance(event.content, dict) else {}
                title = plot_data.get("title", "Interactive Plot")
                plot_type = plot_data.get("plot_type", "line")
                series = plot_data.get("series", [])
                x_label = plot_data.get("x_label", "x")
                y_label = plot_data.get("y_label", "y")
                math_formula = plot_data.get("math_formula", "")
                quantum_n = plot_data.get("quantum_n", 0)
                domain = plot_data.get("domain", [])

                try:
                    plot_widget = self.query_one("#interactive-plot", InteractivePlotWidget)
                    plot_widget.add_class("plot-active")
                    plot_widget.styles.display = "block"
                    if quantum_n is not None:
                        plot_widget.quantum_n = quantum_n
                    plot_widget.post_message(
                        DisplayPlot(
                            title=title,
                            plot_type=plot_type,
                            series=series,
                            x_label=x_label,
                            y_label=y_label,
                            math_formula=math_formula,
                            quantum_n=quantum_n,
                            domain=domain,
                        )
                    )
                except Exception:
                    pass

                msg_log.messages = list(msg_log.messages) + [
                    {
                        "role": "plot",
                        "content": title,
                        "metadata": {"plot_data": plot_data},
                    }
                ]
                status_widget.tool_status = "success"

            elif event.kind == "error":
                status_widget.tool_status = "error"
                msg_log.messages = list(msg_log.messages) + [
                    {"role": "error", "content": str(event.content)}
                ]

            elif event.kind == "status":
                status_content = str(event.content)
                meta = event.metadata or {}
                if meta.get("verification"):
                    status_widget.tool_status = "success"
                    status_widget.last_verification = status_content
                    msg_log.messages = list(msg_log.messages) + [
                        {"role": "system", "content": status_content, "metadata": meta}
                    ]
                elif meta.get("busy"):
                    status_widget.tool_status = "running"
                    status_widget.agent_name = status_content
                else:
                    msg_log.messages = list(msg_log.messages) + [
                        {"role": "system", "content": status_content, "metadata": meta}
                    ]

            elif event.kind == "comprehension":
                try:
                    score = float(event.content)
                    journey_widget.post_message(
                        JourneyProgressChanged(
                            topic=journey_widget.topic,
                            progress=score,
                            mastered_count=journey_widget.mastered_count,
                            total_count=journey_widget.total_count,
                        )
                    )
                except (ValueError, TypeError):
                    pass

            elif event.kind == "subconcepts":
                if isinstance(event.content, list):
                    active_sub = getattr(
                        getattr(controller, "teaching_session", None),
                        "current_subconcept",
                        None,
                    )
                    active_name = active_sub.name if active_sub else ""
                    tree_widget.post_message(
                        ConceptUpdated(
                            concepts=event.content,
                            active_concept=active_name,
                            topic=str(getattr(controller, "topic", "Curriculum")).title(),
                        )
                    )
                    mastered = sum(
                        1
                        for sc in event.content
                        if isinstance(sc, dict) and sc.get("mastery", 0.0) >= 0.8
                    )
                    total = len(event.content)
                    prog = (mastered / total) if total > 0 else 0.0
                    journey_widget.post_message(
                        JourneyProgressChanged(
                            topic=str(getattr(controller, "topic", "General")).title(),
                            progress=prog,
                            mastered_count=mastered,
                            total_count=total,
                        )
                    )

            elif event.kind == "state_changed":
                msg_count = getattr(controller, "message_count", 0)
                toks = msg_count * 120
                cost = toks * 0.000005
                status_widget.post_message(
                    DiagnosticsUpdated(
                        tokens=toks,
                        latency_s=status_widget.latency_s,
                        cost_usd=cost,
                        velocity_tps=status_widget.velocity_tps,
                        tool_status=status_widget.tool_status,
                        last_verification=status_widget.last_verification,
                    )
                )
                memory_widget.memory_count = msg_count * 2
                topic = getattr(controller, "topic", "General")
                journey_widget.topic = str(topic).title()
                tree_widget.topic_name = str(topic).title()


