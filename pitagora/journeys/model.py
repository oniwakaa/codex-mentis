"""LearningJourney — a persistent record of a teaching session's progress.

A journey wraps a TeachingSession's serialized state plus aggregate progress
metrics (mastery, comprehension history, style effectiveness) so a learner can
pause and resume across restarts. Stored as JSON by journeys/store.py.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


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


class JourneyStatus(StrEnum):
    active = "active"
    paused = "paused"
    completed = "completed"
    abandoned = "abandoned"


@dataclass
class LearningJourney:
    topic: str
    user_level: str = "intermediate"
    status: str = JourneyStatus.active.value
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    sub_concepts: list[dict[str, Any]] = field(default_factory=list)
    comprehension_history: list[float] = field(default_factory=list)
    style_effectiveness: dict[str, Any] = field(default_factory=dict)
    interaction_count: int = 0
    # Serialized TeachingSession state (its to_dict() output).
    session_state: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = _utc_now()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LearningJourney:
        if not isinstance(d, dict):
            raise TypeError("journey data must be an object")
        if not isinstance(d.get("topic"), str) or not d["topic"].strip():
            raise ValueError("journey topic is required")

        migrated = dict(d)
        migrated.setdefault("created_at", migrated.get("started_at"))
        migrated.setdefault("updated_at", migrated.get("last_active"))
        migrated.setdefault("interaction_count", migrated.get("total_interactions", 0))

        known = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in migrated.items() if k in known}
        journey = cls(**clean)
        journey.created_at = _timestamp(clean.get("created_at"), journey.created_at)
        journey.updated_at = _timestamp(clean.get("updated_at"), journey.created_at)
        return journey

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, data: str) -> LearningJourney:
        return cls.from_dict(json.loads(data))

    def to_markdown(self) -> str:
        lines = [
            f"# Learning Journey: {self.topic}",
            "",
            f"- Status: {self.status}",
            f"- Level: {self.user_level}",
            f"- Interactions: {self.interaction_count}",
            "",
            "## Sub-concepts",
        ]
        if not self.sub_concepts:
            lines.append("- None yet")
        for concept in self.sub_concepts:
            name = concept.get("name", "?")
            mastery = float(concept.get("mastery", concept.get("mastery_score", 0.0)))
            marker = "x" if concept.get("visited", False) else " "
            lines.append(f"- [{marker}] {name} — {mastery:.0%}")
        return "\n".join(lines) + "\n"


def demo() -> None:
    j = LearningJourney(
        topic="limits", sub_concepts=[{"name": "def", "mastery": 0.8, "visited": True}]
    )
    j.interaction_count = 3
    j.comprehension_history = [0.1, 0.25, 0.4]
    blob = j.to_json()
    j2 = LearningJourney.from_json(blob)
    assert j2.topic == "limits"
    assert j2.sub_concepts[0]["name"] == "def"
    assert j2.interaction_count == 3
    print("journey model demo ok")


if __name__ == "__main__":
    demo()
