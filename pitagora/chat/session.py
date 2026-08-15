"""Chat session state management."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pitagora import chat as chat_runtime
from pitagora.sessions import list_sessions, load_session, save_session

log = logging.getLogger(__name__)


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


class ChatSessionState:
    """Encapsulates chat session state and session manipulation commands."""

    def __init__(
        self,
        mode: str = "study",
        topic: str = "general",
        system_prompt: str | None = None,
        config: dict[str, Any] | None = None,
        completion: Any = None,
        rag_lookup: Any = None,
        concept_lookup: Any = None,
        memory_lookup: Any = None,
        verify_math: Any = None,
        save_memory: Any = None,
        record_study: Any = None,
        due_reviews: Any = None,
        user_context: str | None = None,
        feedback_loop: tuple[Any, Any, Any] | None = None,
    ) -> None:
        self.mode = mode
        self.topic = topic
        self.config = config or chat_runtime.load_provider_config()
        self.model = self.config.get("default_model", "unknown")
        self.completion = completion or chat_runtime.chat_completion
        self.rag_lookup = rag_lookup or chat_runtime._get_rag_context
        self.concept_lookup = concept_lookup or chat_runtime._get_concept_context
        self.memory_lookup = memory_lookup or getattr(chat_runtime, "_get_memory_context", None)
        self.verify_math = verify_math or chat_runtime._verify_math
        self.save_memory = save_memory or chat_runtime._save_to_memory
        self.record_study = record_study or chat_runtime._record_study
        self.due_reviews = due_reviews or chat_runtime._check_due_reviews

        self.started_at = datetime.now()
        self.message_count = 0
        self.teaching_session: Any = None
        self.teaching_analyzer: Any = None
        self.teaching_journey: Any = None
        self.last_freeform = {"topic": topic, "strategy": "socratic"}
        self.system_prompt = system_prompt or self._default_system_prompt()
        context_text = chat_runtime._get_user_context() if user_context is None else user_context
        if context_text:
            self.system_prompt += f"\n\n{context_text}"
        self.messages = [{"role": "system", "content": self.system_prompt}]
        loop = chat_runtime._build_feedback_loop() if feedback_loop is None else feedback_loop
        (
            self.feedback_improver,
            self.feedback_skill_evo,
            self.feedback_skills_engine,
        ) = loop

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are Pitagora, an advanced, highly proactive AI tutor and reasoning engine "
            "for mathematics and physics.\n\n"
            "Core Pedagogical Principles:\n"
            "1. BIAS FOR ACTION & DIRECT DEMONSTRATION: Do not trap the user in passive, "
            "open-ended Socratic question loops. When introducing or explaining concepts "
            "(e.g., Quantum Mechanics, Wave-Particle Duality, Harmonic Oscillators), immediately "
            "provide the core mathematical formulation, precise physical intuition, and an "
            "interactive exploration hook (e.g., concrete code simulation, mathematical derivation, "
            "or visual plot commands like `/plot`).\n"
            "2. CONCRETE CONCEPTUAL BREAKDOWN: Give rigorous, structured explanations with "
            "exact formulas and physical meaning for each variable.\n"
            "3. MATHEMATICAL PRECISION: Always use clean LaTeX notation ($...$ inline, $$...$$ display) "
            "and proper Dirac/operator notation (|ψ⟩, ⟨x|, Â, ħ, ℂ, ∫, ∑). Never emit broken escape sequences.\n"
            "4. ACTIONABLE CLOSING: Conclude explanations with concrete next actions, parameter "
            "explorations (e.g., 'Try varying n from 1 to 4', 'Inspect the barrier width a'), or "
            "targeted exercises rather than generic multiple-choice or diagnostic questions."
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
            "sub_concepts": ([item.to_dict() for item in session.sub_concepts] if session else []),
            "journey": getattr(self.teaching_journey, "topic", None),
            "journey_progress": (
                (session.current_index + 1) / len(session.sub_concepts)
                if session and session.sub_concepts
                else 0.0
            ),
            "due_reviews": self.due_reviews(),
        }

    def cmd_mode(self, argument: str):
        if not argument:
            yield ChatEvent("status", f"Current mode: {self.mode}")
            return
        self.mode = argument
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def cmd_topic(self, argument: str):
        if not argument:
            yield ChatEvent("status", f"Current topic: {self.topic}")
            return
        self.topic = argument
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def cmd_model(self, argument: str):
        if not argument:
            yield ChatEvent("status", f"Current model: {self.model}")
            return
        self.config["default_model"] = argument
        self.model = argument
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def cmd_clear(self, argument: str):
        self.messages = [{"role": "system", "content": self.system_prompt}]
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def cmd_save(self, argument: str):
        sid = save_session(self.messages, topic=self.topic, mode=self.mode)
        yield ChatEvent("status", f"✓ Session saved: {sid}")
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def cmd_sessions(self, argument: str):
        sessions = list_sessions()
        if not sessions:
            yield ChatEvent("status", "No saved sessions.")
            return
        lines = [
            f"  {s['id']} — {s['topic']} ({s['mode']}) — {s['message_count']} msgs"
            for s in sessions
        ]
        yield ChatEvent("markdown", "\n".join(lines))

    def cmd_resume(self, argument: str):
        if argument:
            sid: str | None = argument
        else:
            sessions = list_sessions(limit=1)
            sid = str(sessions[0]["id"]) if sessions else None
        if sid:
            loaded = load_session(sid)
            if loaded:
                self.messages = loaded
                yield ChatEvent("status", f"✓ Resumed session {sid} ({len(loaded)} messages)")
            else:
                yield ChatEvent("error", f"Session not found: {sid}")
        else:
            yield ChatEvent("status", "No sessions to resume.")
        yield ChatEvent("state_changed", metadata={"context": self.context})
