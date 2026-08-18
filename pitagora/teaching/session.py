"""TeachingSession — state machine for guided interactive learning.

States flow:
    introducing → exploring ↔ checking ↔ adapting → visualizing / quizzing
        → reviewing → completed
    Any state may transition to paused; paused resumes to its prior state.

Comprehension score (0.0-1.0) is a smoothed EMA of per-interaction deltas.
Style effectiveness tracks which explanation styles (feynman, formal, visual,
historical, socratic, applied) work best for this learner.

Serializable to a plain dict for JSON persistence (see journeys/store.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class TeachingState(StrEnum):
    introducing = "introducing"
    exploring = "exploring"
    checking = "checking"
    adapting = "adapting"
    visualizing = "visualizing"
    quizzing = "quizzing"
    reviewing = "reviewing"
    paused = "paused"
    completed = "completed"


# Single-character shortcuts the user can type instead of a free-form reply.
SHORTCUTS: dict[str, str] = {
    "n": "next",
    "e": "explain_differently",
    "d": "go_deeper",
    "s": "skip",
    "?": "confused",
    "v": "visualize",
    "q": "quiz",
    "p": "pause",
    "r": "resume",
    "h": "help",
}

ALL_STYLES = ("feynman", "formal", "visual", "historical", "socratic", "applied")
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
LEVEL_DIFFICULTY = {"beginner": 1, "intermediate": 3, "advanced": 4}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _timestamp(value: Any, default: str) -> str:
    if not isinstance(value, str) or not value:
        return default
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return default
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


@dataclass
class StyleEffectiveness:
    """Tracks per-style success rate. `attempts` feeds the EMA so a style
    that works once isn't crowned on a single sample."""

    attempts: dict[str, int] = field(default_factory=lambda: {s: 0 for s in ALL_STYLES})
    success: dict[str, float] = field(default_factory=lambda: {s: 0.0 for s in ALL_STYLES})

    def record(self, style: str, delta: float) -> None:
        if style not in self.attempts:
            return
        self.attempts[style] += 1
        # EMA: weight recent interactions. Positive delta = success.
        reward = 1.0 if delta > 0 else 0.0
        a = self.attempts[style]
        self.success[style] = self.success[style] + (reward - self.success[style]) / a

    def reject(self, style: str) -> None:
        """Record an explicit request not to use this style again."""
        if style in self.attempts:
            self.attempts[style] += 1
            self.success[style] = 0.0

    def best(self) -> str:
        if not any(self.attempts.values()):
            return ALL_STYLES[0]
        # Untried styles start at a neutral prior so an explicitly rejected
        # style yields to the next available teaching style.
        return max(
            ALL_STYLES,
            key=lambda style: self.success[style] if self.attempts[style] else 0.5,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"attempts": self.attempts, "success": self.success}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StyleEffectiveness:
        se = cls()
        if not d:
            return se
        if "attempts" not in d and "success" not in d:
            for style in ALL_STYLES:
                if style in d:
                    se.attempts[style] = 1
                    se.success[style] = float(d[style])
            return se
        for s in ALL_STYLES:
            se.attempts[s] = int(d.get("attempts", {}).get(s, 0))
            se.success[s] = float(d.get("success", {}).get(s, 0.0))
        return se


@dataclass
class SubConcept:
    name: str
    mastery: float = 0.0
    visited: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "mastery": self.mastery, "visited": self.visited}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SubConcept:
        mastery = d.get("mastery", d.get("mastery_score", 0.0))
        status = d.get("status")
        return cls(
            name=d["name"],
            mastery=max(0.0, min(1.0, float(mastery))),
            visited=bool(d.get("visited", status in {"active", "mastered", "skipped"})),
        )


class TeachingSession:
    """State machine driving a single teaching session over one topic.

    The session is deliberately provider-agnostic: it holds state and
    transition logic only. LLM calls live in ResponseAnalyzer and the chat
    loop; the session just consumes their classification outputs.
    """

    def __init__(
        self,
        topic: str,
        sub_concepts: list[str] | None = None,
        user_level: str = "intermediate",
    ) -> None:
        self.topic = topic
        self.user_level = user_level
        self.sub_concepts: list[SubConcept] = [SubConcept(name=n) for n in (sub_concepts or [])]
        self.current_index: int = 0
        self.state: TeachingState = TeachingState.introducing
        self._prior_state: TeachingState = TeachingState.introducing
        self.comprehension_score: float = 0.0
        self.ema_alpha: float = 0.3  # comprehension smoothing
        self.style_effectiveness: StyleEffectiveness = StyleEffectiveness()
        self.history: list[dict[str, Any]] = []
        self.current_style: str = "feynman"
        self.difficulty_level: int = LEVEL_DIFFICULTY.get(user_level.lower(), 3)
        self.created_at: str = _utc_now()
        self.updated_at: str = self.created_at
        self.interaction_count: int = 0

    # ─── sub-concepts ───

    @property
    def current_subconcept(self) -> SubConcept | None:
        if 0 <= self.current_index < len(self.sub_concepts):
            return self.sub_concepts[self.current_index]
        return None

    def set_sub_concepts(self, names: list[str]) -> None:
        """Replace the sub-concept list (used after LLM generation)."""
        self.sub_concepts = [SubConcept(name=n) for n in names]
        self.current_index = 0

    # ─── state transitions ───

    def transition(self, new_state: TeachingState) -> None:
        if self.state == TeachingState.paused and new_state != TeachingState.paused:
            # resuming — restore prior state unless caller explicitly passes a
            # different state, in which case honor it.
            if new_state == self._prior_state:
                self.state = self._prior_state
            else:
                self.state = new_state
            self._touch()
            return
        if new_state == TeachingState.paused:
            self._prior_state = self.state
        self.state = new_state
        self._touch()

    def pause(self) -> None:
        if self.state != TeachingState.paused:
            self._prior_state = self.state
            self.state = TeachingState.paused
            self._touch()

    def resume(self) -> None:
        if self.state == TeachingState.paused:
            self.state = self._prior_state
            self._touch()

    def _touch(self) -> None:
        self.updated_at = _utc_now()

    # ─── comprehension + style tracking ───

    def apply_classification(
        self,
        classification: str,
        delta: float,
        style: str | None = None,
        bloom_level: str = "understand",
        cognitive_load: str = "optimal",
    ) -> None:
        """Apply a response classification's comprehension delta and record
        style effectiveness. Called by the chat loop after ResponseAnalyzer."""
        self.interaction_count += 1
        # EMA update
        self.comprehension_score = self.comprehension_score + self.ema_alpha * (
            delta - self.comprehension_score
        )
        # Clamp
        self.comprehension_score = max(0.0, min(1.0, self.comprehension_score))

        if classification == "different_style" and style:
            self.style_effectiveness.reject(style)
            self.current_style = self.style_effectiveness.best()
        elif style:
            self.style_effectiveness.record(style, delta)

        self.regulate_difficulty(classification, bloom_level=bloom_level, cognitive_load=cognitive_load)

        # Update current sub-concept mastery using the classification delta
        sc = self.current_subconcept
        if sc:
            sc.visited = True
            sc.mastery = max(0.0, min(1.0, sc.mastery + delta))

        self.history.append(
            {
                "classification": classification,
                "delta": delta,
                "style": style,
                "state": self.state.value,
                "comprehension": self.comprehension_score,
                "difficulty_level": self.difficulty_level,
                "bloom_level": bloom_level,
                "cognitive_load": cognitive_load,
                "at": _utc_now(),
            }
        )
        self._touch()

    def regulate_difficulty(
        self,
        classification: str,
        bloom_level: str = "understand",
        cognitive_load: str = "optimal",
    ) -> int:
        """Keep task difficulty in a minimal 1–5 ZPD band.

        Explicit learner signals are the least ambiguous regulation input:
        ``deeper`` raises the challenge and ``confused`` lowers it.
        """
        if classification == "deeper" or bloom_level in {"evaluate", "create"}:
            self.difficulty_level = min(MAX_DIFFICULTY, self.difficulty_level + 1)
        elif classification == "confused" or cognitive_load == "overloaded":
            self.difficulty_level = max(MIN_DIFFICULTY, self.difficulty_level - 1)
        return self.difficulty_level

    # ─── shortcuts ───

    @staticmethod
    def is_shortcut(text: str) -> bool:
        t = text.strip().lower()
        return t in SHORTCUTS

    @staticmethod
    def shortcut_action(text: str) -> str | None:
        return SHORTCUTS.get(text.strip().lower())

    def handle_shortcut(self, text: str) -> str | None:
        """Return the action name for a shortcut, applying state side-effects
        for pause/resume/help. Returns None if not a shortcut."""
        action = self.shortcut_action(text)
        if action is None:
            return None
        if action == "pause":
            self.pause()
        elif action == "resume":
            self.resume()
        return action

    # ─── next-action policy ───

    def next_action(self, classification: str) -> str:
        """Decide the next teaching action given a response classification.
        Returns one of: introduce, explain, check, adapt, visualize, quiz,
        review, advance, complete, pause."""
        st = self.state
        if st == TeachingState.completed:
            return "complete"
        if st == TeachingState.paused:
            return "pause"
        if st == TeachingState.reviewing:
            return "complete"
        if classification == "visualize":
            return "visualize"
        if classification == "quiz":
            return "quiz"
        if classification in {
            "off_topic",
            "question",
            "deeper",
            "different_style",
            "confused",
        }:
            return "adapt"
        if classification == "skip":
            return self._advance_or_complete()
        if classification == "correct":
            if st == TeachingState.checking:
                return self._advance_or_complete()
            return "check"
        if classification == "partial":
            if st == TeachingState.checking:
                return "adapt"
            return "check"
        # default
        return "explain"

    def _advance_or_complete(self) -> str:
        if self.current_index < len(self.sub_concepts) - 1:
            self.current_index += 1
            self.state = TeachingState.exploring
            self._touch()
            return "advance"
        self.state = TeachingState.reviewing
        self._touch()
        return "review"

    def complete(self) -> None:
        self.state = TeachingState.completed
        self._touch()

    # ─── serialization ───

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "user_level": self.user_level,
            "sub_concepts": [sc.to_dict() for sc in self.sub_concepts],
            "current_index": self.current_index,
            "state": self.state.value,
            "prior_state": self._prior_state.value,
            "comprehension_score": self.comprehension_score,
            "ema_alpha": self.ema_alpha,
            "style_effectiveness": self.style_effectiveness.to_dict(),
            "current_style": self.current_style,
            "difficulty_level": self.difficulty_level,
            "history": self.history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "interaction_count": self.interaction_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TeachingSession:
        raw_sub_concepts = d.get("sub_concepts", [])
        if not isinstance(raw_sub_concepts, list):
            raw_sub_concepts = []
        s = cls(
            topic=d["topic"],
            sub_concepts=[sc["name"] for sc in raw_sub_concepts],
            user_level=d.get("user_level", "intermediate"),
        )
        s.sub_concepts = [SubConcept.from_dict(sc) for sc in raw_sub_concepts]
        raw_index = d.get("current_index", d.get("current_sub_concept_idx", 0))
        s.current_index = max(0, int(raw_index))
        if s.sub_concepts:
            s.current_index = min(s.current_index, len(s.sub_concepts) - 1)

        try:
            s.state = TeachingState(d.get("state", "introducing"))
        except ValueError:
            s.state = TeachingState.introducing
        history = d.get("history", d.get("interaction_history", []))
        s.history = history if isinstance(history, list) else []
        prior_state = d.get("prior_state", d.get("previous_state"))
        if prior_state is None and s.state == TeachingState.paused:
            for interaction in reversed(s.history):
                candidate = interaction.get("state") if isinstance(interaction, dict) else None
                if candidate and candidate != TeachingState.paused.value:
                    prior_state = candidate
                    break
        try:
            s._prior_state = TeachingState(prior_state or TeachingState.introducing.value)
        except ValueError:
            s._prior_state = TeachingState.introducing
        s.comprehension_score = float(d.get("comprehension_score", 0.0))
        s.ema_alpha = float(d.get("ema_alpha", 0.3))
        s.style_effectiveness = StyleEffectiveness.from_dict(d.get("style_effectiveness", {}))
        current_style = d.get("current_style", d.get("preferred_style", "feynman"))
        s.current_style = current_style if current_style in ALL_STYLES else "feynman"
        raw_difficulty = d.get("difficulty_level", d.get("difficulty", s.difficulty_level))
        s.difficulty_level = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, int(raw_difficulty)))
        s.created_at = _timestamp(d.get("created_at"), s.created_at)
        s.updated_at = _timestamp(
            d.get("updated_at", d.get("last_active")),
            s.created_at,
        )
        s.interaction_count = int(
            d.get("interaction_count", d.get("total_interactions", len(s.history)))
        )
        return s

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, data: str) -> TeachingSession:
        return cls.from_dict(json.loads(data))


def demo() -> None:
    """Self-check: state transitions, shortcut parse, save/load round-trip."""
    s = TeachingSession("limits", ["definition", "epsilon-delta", "examples"])
    assert s.state == TeachingState.introducing
    s.transition(TeachingState.exploring)
    assert s.state == TeachingState.exploring
    s.apply_classification("correct", 0.15, style="feynman")
    assert 0 < s.comprehension_score < 0.15
    assert s.style_effectiveness.attempts["feynman"] == 1
    assert s.is_shortcut("n") and s.shortcut_action("?") == "confused"
    s.pause()
    assert s.state == TeachingState.paused
    s.resume()
    assert s.state == TeachingState.exploring
    blob = s.to_json()
    s2 = TeachingSession.from_json(blob)
    assert s2.topic == s.topic
    assert s2.comprehension_score == s.comprehension_score
    assert s2.sub_concepts[1].name == "epsilon-delta"
    print("session demo ok")


if __name__ == "__main__":
    demo()
