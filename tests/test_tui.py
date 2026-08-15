import pytest

from pitagora.tui import PitagoraApp


@pytest.mark.asyncio
async def test_tui_app_mounts_and_switches_screens():
    app = PitagoraApp()
    async with app.run_test(size=(120, 40)):
        assert app.is_mounted
        assert "chat" in app.SCREENS
        assert "dashboard" in app.SCREENS
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
        assert len(log_widget.messages) == 1
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
