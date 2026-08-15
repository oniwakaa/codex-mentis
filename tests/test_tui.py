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
