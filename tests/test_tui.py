import pytest

from pitagora.chat_controller import ChatEvent
from pitagora.cli.tui import PitagoraApp


class FakeController:
    context = {
        "mode": "study",
        "topic": "limits",
        "model": "test-model",
        "message_count": 0,
        "elapsed_seconds": 0,
        "teaching": False,
        "comprehension": 0.0,
        "sub_concepts": [],
        "journey": None,
        "due_reviews": None,
    }

    def __init__(self):
        self.received = []

    def handle_input(self, text):
        self.received.append(text)
        return iter([ChatEvent("markdown", "answer")])


@pytest.mark.asyncio
async def test_shell_mounts_and_focuses_composer():
    app = PitagoraApp(controller=FakeController())
    async with app.run_test(size=(120, 40)):
        assert "△ PITAGORA" in app.query_one("#brand").render().plain
        assert app.query_one("#composer").has_focus
        assert app.query_one("#sidebar").display is True
        assert "Think. Prove. Understand." in app.query_one(
            "#conversation"
        ).renderable_text


@pytest.mark.asyncio
async def test_sidebar_hides_below_100_columns():
    app = PitagoraApp(controller=FakeController())
    async with app.run_test(size=(80, 30)):
        assert app.query_one("#sidebar").display is False


@pytest.mark.asyncio
async def test_compact_mode_hides_sidebar():
    app = PitagoraApp(controller=FakeController())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+x")
        assert app.has_class("compact")
        assert app.query_one("#sidebar").display is False

@pytest.mark.asyncio
async def test_enter_sends_and_shift_enter_inserts_newline():
    app = PitagoraApp(controller=FakeController())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("h", "i", "shift+enter", "t", "h", "e", "r", "e")
        assert app.query_one("#composer").text == "hi\nthere"
        await pilot.press("enter")
        await pilot.pause()
        assert app.query_one("#composer").text == ""


@pytest.mark.asyncio
async def test_multiline_paste_submits_as_one_message():
    controller = FakeController()
    app = PitagoraApp(controller=controller)
    async with app.run_test(size=(120, 40)) as pilot:
        composer = app.query_one("#composer")
        composer.insert("first line\nsecond line")
        await pilot.press("enter")
        await pilot.pause()
        assert controller.received == ["first line\nsecond line"]


@pytest.mark.asyncio
async def test_slash_opens_autocomplete_and_tab_completes():
    app = PitagoraApp(controller=FakeController())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("/")
        assert app.query_one("#command-popup").display is True
        await pilot.press("h", "e", "tab")
        assert app.query_one("#composer").text == "/help"
