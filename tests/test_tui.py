import threading
from rich.table import Table
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

class EventController(FakeController):
    def handle_input(self, text):
        table = Table()
        table.add_column("Value")
        table.add_row("42")
        return iter(
            [
                ChatEvent("user", text),
                ChatEvent("status", "Thinking..."),
                ChatEvent("markdown", "Result\\n\\n$$x^2$$"),
                ChatEvent("renderable", table),
                ChatEvent("comprehension", 0.75),
                ChatEvent(
                    "subconcepts",
                    [{"name": "Squares", "mastery": 0.8, "visited": True}],
                    {"current_index": 0},
                ),
                ChatEvent("controls"),
                ChatEvent("state_changed", metadata={"context": self.context}),
            ]
        )


class BlockingController(FakeController):
    def __init__(self):
        super().__init__()
        self.release = threading.Event()

    def handle_input(self, text):
        self.received.append(text)
        self.release.wait(timeout=2)
        return iter([ChatEvent("markdown", "done")])


@pytest.mark.asyncio
async def test_events_render_as_distinct_widgets():
    app = PitagoraApp(controller=EventController())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("h", "i", "enter")
        import asyncio
        await asyncio.sleep(0.1)
        await pilot.pause()
        
        texts = []
        for child in app.query_one("#conversation").children:
            if hasattr(child, "renderable_text"):
                texts.append(child.renderable_text)
            elif hasattr(child, "render"):
                try:
                    texts.append(str(child.render().plain) if hasattr(child.render(), "plain") else str(child.render()))
                except Exception:
                    texts.append(str(child))
            else:
                texts.append(str(child))
        
        # Let's extract text by walking the tree
        def walk(widget):
            res = []
            if hasattr(widget, "renderable_text"): res.append(widget.renderable_text)
            try: 
                if hasattr(widget, "render") and hasattr(widget.render(), "plain"): res.append(widget.render().plain)
            except Exception: pass
            if hasattr(widget, "text"): res.append(widget.text)
            if hasattr(widget, "document"): res.append(str(widget.document))
            for c in widget.children:
                res.extend(walk(c))
            return res
        
        text = " ".join(walk(app.query_one("#conversation")))

        assert "△ you>" in text
        assert "Result" in text
        assert "42" in text
        assert "75.0% comprehension" in text
        assert "[n] next" in text


@pytest.mark.asyncio
async def test_clear_visible_keeps_controller_context():
    controller = EventController()
    app = PitagoraApp(controller=controller)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("h", "i", "enter")
        import asyncio
        await asyncio.sleep(0.1)
        await pilot.pause()
        await pilot.press("ctrl+l")
        assert "Result" not in app.query_one("#conversation").renderable_text
        assert controller.context["topic"] == "limits"


@pytest.mark.asyncio
async def test_busy_state_rejects_second_submission():
    controller = BlockingController()
    app = PitagoraApp(controller=controller)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("o", "n", "e", "enter")
        await pilot.pause()
        assert app.query_one("#composer").read_only is True
        # For the fake submission, post the message directly to bypass key handling
        from pitagora.cli.tui_widgets import ChatTextArea
        app.query_one("#composer").post_message(ChatTextArea.Submitted(app.query_one("#composer"), "two"))
        controller.release.set()
        await pilot.pause()
        assert controller.received == ["one"]
