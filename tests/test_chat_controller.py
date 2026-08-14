"""Tests for the shared ChatController.

The controller is a headless state machine: it depends on injected callables
for completion, RAG, memory, etc., and emits ChatEvent objects. These tests
cover the free-form study turn path and the controller's neutral contract.
"""

from pitagora.chat_controller import ChatController, ChatEvent


def make_controller(completion=lambda messages, model=None, config=None: "answer", **overrides):
    defaults = dict(
        mode="study",
        topic="limits",
        config={"default_model": "test-model"},
        completion=completion,
        rag_lookup=lambda query: "[rag]",
        concept_lookup=lambda topic: "[concept]",
        verify_math=lambda response: None,
        save_memory=lambda role, content, topic: None,
        record_study=lambda topic, user_input: None,
        due_reviews=lambda: None,
        user_context="",
        feedback_loop=(None, None, None),
    )
    defaults.update(overrides)
    return ChatController(**defaults)


def test_freeform_turn_emits_user_status_markdown_state_changed():
    controller = make_controller()

    events = list(controller.handle_input("What is a limit?"))

    assert [event.kind for event in events] == [
        "user",
        "status",
        "markdown",
        "state_changed",
    ]
    assert events[0].content == "What is a limit?"
    assert events[2].content == "answer"
    assert controller.messages[-2]["content"].endswith("User question: What is a limit?")
    assert controller.messages[-1] == {"role": "assistant", "content": "answer"}


def test_empty_input_emits_nothing():
    assert list(make_controller().handle_input("   ")) == []


def test_context_reports_session_state():
    controller = make_controller()
    list(controller.handle_input("hello"))

    context = controller.context

    assert context["mode"] == "study"
    assert context["topic"] == "limits"
    assert context["model"] == "test-model"
    assert context["message_count"] == 1
    assert context["teaching"] is False


def test_no_context_path_enriches_with_just_user_question():
    controller = make_controller(
        rag_lookup=lambda query: "",
        concept_lookup=lambda topic: "",
    )

    list(controller.handle_input("Why is the sky blue?"))

    assert controller.messages[-2]["content"] == "Why is the sky blue?"


def test_verification_event_emits_status_with_verification_metadata():
    controller = make_controller(verify_math=lambda response: "Math looks off")

    events = list(controller.handle_input("derive something"))

    status_events = [e for e in events if e.kind == "status"]
    assert len(status_events) == 2
    assert status_events[0].content == "Thinking..."
    assert status_events[0].metadata == {"busy": True}
    assert status_events[1].content == "Math looks off"
    assert status_events[1].metadata == {"verification": True}


def test_save_memory_called_with_correct_args():
    calls = []
    controller = make_controller(
        save_memory=lambda role, content, topic: calls.append((role, content, topic)),
    )

    list(controller.handle_input("explain limits"))

    assert ("user", "explain limits", "limits") in calls
    assert ("assistant", "answer", "limits") in calls
    assert len(calls) == 2


def test_record_study_called_with_correct_args():
    calls = []
    controller = make_controller(
        record_study=lambda topic, user_input: calls.append((topic, user_input)),
    )

    list(controller.handle_input("explain limits"))

    assert calls == [("limits", "explain limits")]


def test_custom_system_prompt_appears_in_messages():
    controller = make_controller(system_prompt="You are a custom tutor.")

    assert controller.messages[0]["content"] == "You are a custom tutor."


def test_user_context_appended_to_system_prompt():
    controller = make_controller(user_context="[User profile: Alice]")

    assert controller.messages[0]["content"].startswith("You are Pitagora")
    assert controller.messages[0]["content"].endswith("[User profile: Alice]")


def test_controller_is_neutral_no_io_when_deps_injected(capsys):
    controller = make_controller()

    list(controller.handle_input("neutral turn"))

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# ─── Command dispatch parity and state tests (Task 4) ───

from pitagora.cli.repl_input import COMMAND_TREE


def test_controller_has_handler_for_every_repl_command():
    assert set(COMMAND_TREE).issubset(ChatController.COMMANDS)


def test_mode_topic_and_model_commands_update_context():
    controller = make_controller()

    list(controller.handle_input("/mode reason"))
    list(controller.handle_input("/topic derivatives"))
    list(controller.handle_input("/model another-model"))

    assert controller.context["mode"] == "reason"
    assert controller.context["topic"] == "derivatives"
    assert controller.context["model"] == "another-model"


def test_clear_resets_messages_but_keeps_system_prompt():
    controller = make_controller()
    list(controller.handle_input("hello"))

    events = list(controller.handle_input("/clear"))

    assert controller.messages == [{"role": "system", "content": controller.system_prompt}]
    assert events[-1].kind == "state_changed"


def test_quit_emits_quit_request():
    events = list(make_controller().handle_input("/quit"))

    assert events[-1].metadata["quit"] is True


def test_unknown_command_is_visible():
    events = list(make_controller().handle_input("/not-real"))

    assert events == [ChatEvent("error", "Unknown: /not-real. /help for commands.")]


# ─── Teaching mode tests (Task 5) ───

from pitagora.journeys.model import LearningJourney
from pitagora.teaching.analyzer import ResponseClassification
from pitagora.teaching.session import TeachingSession, TeachingState


class CorrectAnalyzer:
    def classify(self, text, topic, sub_concept, config=None, model=None):
        return ResponseClassification(
            label="correct",
            delta=0.15,
            rationale="test",
            via_shortcut=text == "n",
        )


def test_explore_starts_teaching_and_emits_inline_widgets(monkeypatch):
    controller = make_controller()
    monkeypatch.setattr(
        "pitagora.chat_controller.chat_runtime._generate_sub_concepts",
        lambda topic, config, model: ["Definition", "Examples"],
    )
    monkeypatch.setattr(
        "pitagora.chat_controller.ResponseAnalyzer",
        lambda completion: CorrectAnalyzer(),
    )
    monkeypatch.setattr(
        "pitagora.journeys.store.get_or_create_journey",
        lambda topic, subs: LearningJourney(
            topic=topic,
            sub_concepts=[{"name": n, "mastery": 0.0, "visited": False} for n in subs],
        ),
    )

    events = list(controller.handle_input("/explore limits"))

    assert controller.teaching_session.topic == "limits"
    assert controller.teaching_session.state in {
        TeachingState.exploring,
        TeachingState.checking,
    }
    assert {"markdown", "comprehension", "subconcepts", "controls"}.issubset(
        {event.kind for event in events}
    )


def test_pause_shortcut_saves_and_leaves_teaching(monkeypatch):
    controller = make_controller()
    controller.teaching_session = TeachingSession("limits", ["Definition"])
    controller.teaching_session.transition(TeachingState.exploring)
    controller.teaching_journey = LearningJourney(
        topic="limits",
        sub_concepts=[{"name": "Definition", "mastery": 0.0, "visited": False}],
    )
    saved = []
    monkeypatch.setattr(
        "pitagora.journeys.store.save_journey",
        lambda journey: saved.append(journey),
    )

    events = list(controller.handle_input("p"))

    assert controller.teaching_session is None
    assert events[-1].kind == "state_changed"
    assert len(saved) == 1 and saved[0].topic == "limits"


# ─── Rich adapter tests (Task 6) ───

from rich.console import Console

from pitagora.chat import launch_chat


class FakeController:
    mode = "study"
    topic = "general"
    model = "test-model"

    def startup_events(self):
        return [ChatEvent("status", "welcome")]

    def handle_input(self, text):
        if text == "/quit":
            return iter(
                [
                    ChatEvent("status", "Goodbye! Keep reasoning."),
                    ChatEvent("state_changed", metadata={"quit": True}),
                ]
            )
        return iter([ChatEvent("markdown", "answer")])


def test_launch_chat_renders_controller_events():
    inputs = iter(["hello", "/quit"])
    console = Console(record=True, width=80)

    launch_chat(
        controller=FakeController(),
        input_reader=lambda mode, topic: next(inputs),
        con=console,
    )

    output = console.export_text()
    assert "answer" in output
    assert "Goodbye! Keep reasoning." in output
