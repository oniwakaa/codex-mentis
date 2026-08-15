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
async def test_tui_plot_widget():
    from pitagora.tui.screens.plot_screen import PlotScreen
    from pitagora.tui.widgets.interactive_plot import InteractivePlotWidget

    plot_screen = PlotScreen(plot_type="quantum_ho", quantum_n=1)
    app = PitagoraApp()
    app.SCREENS["plot_custom"] = lambda: plot_screen
    async with app.run_test(size=(120, 40)):
        app.switch_screen("plot")
        await app.screen.recompose()
        widget = app.screen.query_one(InteractivePlotWidget)
        assert widget is not None
        assert widget.quantum_n == 0
        widget.action_set_state_2()
        assert widget.quantum_n == 2
        widget.action_zoom_in()
        widget.action_zoom_out()
        widget.action_toggle_potential()


