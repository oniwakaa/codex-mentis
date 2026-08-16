import pytest

from pitagora.tui import PitagoraApp


@pytest.mark.asyncio
async def test_tui_app_mounts_and_switches_screens():
    app = PitagoraApp()
    async with app.run_test(size=(120, 40)):
        assert app.is_mounted
        assert "chat" in app.SCREENS
        assert "dashboard" in app.SCREENS
        assert "plot" in app.SCREENS
        assert "settings" in app.SCREENS


@pytest.mark.asyncio
async def test_tui_app_actions():
    app = PitagoraApp()
    async with app.run_test(size=(120, 40)):
        app.action_toggle_reasoning()
        assert app.reasoning_visible is True

        app.action_toggle_diff()
        assert app.diff_visible is True

        app.action_cycle_panels()
        app.action_cancel_op()
        app.action_clear_screen()


@pytest.mark.asyncio
async def test_tui_chat_input_submission():
    app = PitagoraApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("h", "e", "l", "l", "o", "enter")
        await pilot.pause()
        log_widget = app.screen.query_one("#message-log")
        assert len(log_widget.messages) >= 1
        assert log_widget.messages[0]["content"] == "hello"


@pytest.mark.asyncio
async def test_tui_slash_command_execution():
    app = PitagoraApp()
    async with app.run_test(size=(120, 40)):
        app.screen.process_user_input("/topic")
        import asyncio

        await asyncio.sleep(0.1)
        log_widget = app.screen.query_one("#message-log")
        assert len(log_widget.messages) >= 1
        assert any("topic" in str(m.get("content", "")).lower() for m in log_widget.messages)


@pytest.mark.asyncio
async def test_tui_latex_and_message_cards():
    app = PitagoraApp()
    async with app.run_test(size=(120, 40)):
        log_widget = app.screen.query_one("#message-log")
        # Test raw Dirac notation and escape strings
        log_widget.messages = [
            {"role": "user", "content": r"What is \|\psi\rangle = \alpha|0\rangle + \beta|1\rangle?"},
            {"role": "assistant", "content": r"State equation: $$\hat{H}|\psi\rangle = E|\psi\rangle$$ with $\hbar \omega$."},
            {"role": "system", "content": "✓ Verified via SymPy: E = hbar * omega", "metadata": {"verification": True}},
        ]
        renderable = log_widget.render()
        assert renderable is not None
        # Test scrolling methods
        log_widget.scroll_up_lines()
        log_widget.scroll_down_lines()
        log_widget.page_up()
        log_widget.page_down()


@pytest.mark.asyncio
async def test_tui_widgets_render():
    app = PitagoraApp()
    async with app.run_test(size=(120, 40)):
        tree = app.screen.query_one("#concept-tree")
        tree.concepts = [
            {"name": "Quantum Mechanics", "status": "active", "mastery": 0.75},
            {"name": "Linear Algebra", "status": "mastered", "mastery": 1.0},
        ]
        assert tree.render() is not None

        journey = app.screen.query_one("#journey-bar")
        journey.progress = 0.85
        assert journey.render() is not None

        status = app.screen.query_one("#agent-status")
        status.tool_status = "success"
        assert status.render() is not None

        memory = app.screen.query_one("#memory-inspector")
        memory.memory_count = 5
        assert memory.render() is not None


@pytest.mark.asyncio
async def test_tui_inline_plot_card():
    from pitagora.tui.widgets.interactive_plot import InlinePlotCard

    widget = InlinePlotCard(
        plot_type="quantum_ho",
        quantum_n=0,
        title=r"Quantum Wavefunction \psi_0",
        math_formula=r"\psi_0(x) = \pi^{-1/4} e^{-x^2/2}",
    )
    assert widget.quantum_n == 0
    assert widget.loss_variant == "mse"
    widget.quantum_n = 2
    assert widget.quantum_n == 2
    widget.loss_variant = "huber"
    assert widget.loss_variant == "huber"


@pytest.mark.asyncio
async def test_tui_plot_screen_integration():
    from pitagora.tui.screens.plot_screen import PlotScreen
    from pitagora.tui.widgets.interactive_plot import InteractivePlotWidget

    plot_screen = PlotScreen(plot_type="quantum_ho", quantum_n=0)
    assert plot_screen is not None

    widget = InteractivePlotWidget(plot_type="quantum_ho", quantum_n=0)
    assert widget.quantum_n == 0
    widget.action_set_state_2()
    assert widget.quantum_n == 2
    widget.action_zoom_in()
    widget.action_zoom_out()
    widget.action_toggle_potential()
    assert widget.show_potential is False


@pytest.mark.asyncio
async def test_plot_architect_agent_and_payload():
    from pitagora.agents.plot_architect import PlotArchitectAgent
    from pitagora.agents.providers.base import BaseProvider, ProviderConfig

    class _MockProv(BaseProvider):
        def __init__(self):
            super().__init__(ProviderConfig(api_key="k", model="m"))
        def complete(self, messages, **kwargs):
            return {"content": "ok", "tool_calls": []}
        async def acomplete(self, messages, **kwargs):
            return {"content": "ok", "tool_calls": []}
        def stream(self, messages):
            yield ""
        async def astream(self, messages):
            yield ""
        def embed(self, texts):
            return [[0.0] for _ in texts]
        async def aembed(self, texts):
            return [[0.0] for _ in texts]

    agent = PlotArchitectAgent(_MockProv())
    assert agent.should_visualize("Explain the quantum harmonic oscillator wavefunction") is True
    assert agent.should_visualize("Compute dispersion relation in graphene") is True
    assert agent.should_visualize("Definition of integer arithmetic") is False

    payload = agent.generate_plot_payload("quantum harmonic oscillator", quantum_n=2)
    assert payload["plot_type"] == "line"
    assert "series" in payload
    assert len(payload["series"]) >= 2
    assert "math_formula" in payload
    assert payload["quantum_n"] == 2


@pytest.mark.asyncio
async def test_message_log_plot_card_renders_latex_legend():
    from pitagora.tui.widgets.message_log import MessageLogWidget

    app = PitagoraApp()
    async with app.run_test(size=(120, 40)):
        msg_log = app.screen.query_one("#message-log", MessageLogWidget)
        msg_log.messages = [
            {
                "role": "plot",
                "content": r"Quantum State \psi_1",
                "metadata": {
                    "plot_data": {
                        "title": r"Quantum State \psi_1",
                        "plot_type": "line",
                        "x_label": r"Position x (\mu m)",
                        "y_label": r"|\psi(x)|^2",
                        "math_formula": r"\psi(x) = \sqrt{2/L} \sin(\pi x / L)",
                        "series": [
                            {"name": r"|\psi_1(x)|^2 (Density)", "x": [0.0, 1.0, 2.0], "y": [0.0, 1.0, 0.0]},
                            {"name": r"\psi_1(x) (Wave)", "x": [0.0, 1.0, 2.0], "y": [0.0, 1.0, 0.0]},
                        ],
                    }
                },
            }
        ]
        renderable = msg_log.render()
        assert renderable is not None



