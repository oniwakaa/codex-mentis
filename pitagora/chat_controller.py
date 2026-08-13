"""Shared headless chat controller.

The :class:`ChatController` is a pure state machine that drives a Pitagora
conversation. It owns the message list and session metadata and emits
:class:`ChatEvent` objects to its caller (the TUI, a CLI, or a test). All
external dependencies — completion, RAG, memory, spaced repetition — are
injected as callables so the controller never performs I/O of its own when
deps are supplied.

This module delegates to the helpers already living in :mod:`pitagora.chat`
so the existing runtime behaviour is preserved when callers do not inject
their own dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterator, Optional

from pitagora import chat as chat_runtime


@dataclass(frozen=True)
class ChatEvent:
    """A single emitted conversation event.

    ``kind`` is a small string tag the consumer switches on (``"user"``,
    ``"status"``, ``"markdown"``, ``"state_changed"``, ``"error"`` ...).
    ``content`` carries the payload appropriate to the kind and ``metadata``
    holds optional structured flags.
    """

    kind: str
    content: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChatController:
    """Headless conversation controller.

    The controller is intentionally framework-agnostic: it knows nothing
    about Textual, Rich, or the terminal. It produces a stream of
    :class:`ChatEvent` values from :meth:`handle_input` and exposes a
    :attr:`context` snapshot for status bars.
    """

    def __init__(
        self,
        mode: str = "study",
        topic: str = "general",
        system_prompt: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
        completion: Optional[Callable[..., str]] = None,
        rag_lookup: Optional[Callable[[str], str]] = None,
        concept_lookup: Optional[Callable[[str], str]] = None,
        verify_math: Optional[Callable[[str], Optional[str]]] = None,
        save_memory: Optional[Callable[..., None]] = None,
        record_study: Optional[Callable[..., None]] = None,
        due_reviews: Optional[Callable[[], Optional[str]]] = None,
        user_context: Optional[str] = None,
        feedback_loop: Optional[tuple[Any, Any, Any]] = None,
    ) -> None:
        self.mode = mode
        self.topic = topic
        self.config = config or chat_runtime.load_provider_config()
        self.model = self.config.get("default_model", "unknown")
        self.completion = completion or chat_runtime.chat_completion
        self.rag_lookup = rag_lookup or chat_runtime._get_rag_context
        self.concept_lookup = concept_lookup or chat_runtime._get_concept_context
        self.verify_math = verify_math or chat_runtime._verify_math
        self.save_memory = save_memory or chat_runtime._save_to_memory
        self.record_study = record_study or chat_runtime._record_study
        self.due_reviews = due_reviews or chat_runtime._check_due_reviews
        self.started_at = datetime.now()
        self.message_count = 0
        self.teaching_session = None
        self.teaching_analyzer = None
        self.teaching_journey = None
        self.last_freeform = {"topic": topic, "strategy": "socratic"}
        self.system_prompt = system_prompt or self._default_system_prompt()
        context_text = (
            chat_runtime._get_user_context()
            if user_context is None
            else user_context
        )
        if context_text:
            self.system_prompt += f"\n\n{context_text}"
        self.messages = [{"role": "system", "content": self.system_prompt}]
        loop = (
            chat_runtime._build_feedback_loop()
            if feedback_loop is None
            else feedback_loop
        )
        (
            self.feedback_improver,
            self.feedback_skill_evo,
            self.feedback_skills_engine,
        ) = loop
        self._due_review_message = self.due_reviews()

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are Pitagora, an expert mathematics and physics tutor. "
            "You explain concepts clearly using the Socratic method: ask guiding "
            "questions before giving answers. Use LaTeX notation for equations "
            "($..$ inline, $$...$$ display). Be precise, rigorous, and encouraging. "
            "When a student makes a mistake, guide them to discover the error rather "
            "than just correcting it. Use markdown formatting for structure."
        )

    @property
    def context(self) -> dict[str, Any]:
        """Snapshot of session state for status display."""
        session = self.teaching_session
        return {
            "mode": self.mode,
            "topic": self.topic,
            "model": self.model,
            "message_count": self.message_count,
            "elapsed_seconds": int((datetime.now() - self.started_at).total_seconds()),
            "teaching": session is not None,
            "comprehension": session.comprehension_score if session else 0.0,
            "sub_concepts": (
                [item.to_dict() for item in session.sub_concepts] if session else []
            ),
            "journey": getattr(self.teaching_journey, "topic", None),
            "journey_progress": (
                (session.current_index + 1) / len(session.sub_concepts)
                if session and session.sub_concepts
                else 0.0
            ),
            "due_reviews": self._due_review_message,
        }

    def handle_input(self, user_input: str) -> Iterator[ChatEvent]:
        """Dispatch a line of user input to the appropriate handler.

        Empty/whitespace input yields nothing. Lines starting with ``/`` are
        treated as commands. An active teaching session routes to the teaching
        handler. Otherwise the free-form study turn runs.
        """
        text = user_input.strip()
        if not text:
            return
        if text.startswith("/"):
            yield from self._handle_command(text)
            return
        if self.teaching_session is not None:
            yield from self._handle_teaching_turn(text)
            return
        yield from self._handle_freeform_turn(user_input)

    def _handle_freeform_turn(self, user_input: str) -> Iterator[ChatEvent]:
        yield ChatEvent("user", user_input)
        rag_context = self.rag_lookup(user_input)
        concept_context = self.concept_lookup(self.topic)
        contexts = [value for value in (rag_context, concept_context) if value]
        enriched = (
            "\n\n".join(contexts) + f"\n\nUser question: {user_input}"
            if contexts
            else user_input
        )
        self.messages.append({"role": "user", "content": enriched})
        yield ChatEvent("status", "Thinking...", {"busy": True})
        response = self.completion(
            self.messages,
            model=self.model,
            config=self.config,
        )
        self.messages.append({"role": "assistant", "content": response})
        yield ChatEvent("markdown", response)
        verification = self.verify_math(response)
        if verification:
            yield ChatEvent("status", verification, {"verification": True})
        self.save_memory("user", user_input, topic=self.topic)
        self.save_memory("assistant", response, topic=self.topic)
        self.record_study(self.topic, user_input)
        self.message_count += 1
        self.last_freeform = {"topic": self.topic, "strategy": "socratic"}
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def _handle_command(self, text: str) -> Iterator[ChatEvent]:
        yield ChatEvent("error", f"Command unavailable: {text.split()[0]}")

    def _handle_teaching_turn(self, text: str) -> Iterator[ChatEvent]:
        yield ChatEvent("error", "Teaching mode is not initialized.")
