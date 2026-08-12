"""LearningJourney — a persistent record of a teaching session's progress.

A journey wraps a TeachingSession's serialized state plus aggregate progress
metrics (mastery, comprehension history, style effectiveness) so a learner can
pause and resume across restarts. Stored as JSON by journeys/store.py.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class JourneyStatus(str, Enum):
    active = "active"
    paused = "paused"
    completed = "completed"
    abandoned = "abandoned"


@dataclass
class LearningJourney:
    topic: str
    user_level: str = "intermediate"
    status: str = JourneyStatus.active.value
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sub_concepts: List[Dict[str, Any]] = field(default_factory=list)
    comprehension_history: List[float] = field(default_factory=list)
    style_effectiveness: Dict[str, Any] = field(default_factory=dict)
    interaction_count: int = 0
    # Serialized TeachingSession state (its to_dict() output).
    session_state: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LearningJourney":
        # Drop unknown keys defensively so older journey files don't break.
        known = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in d.items() if k in known}
        return cls(**clean)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, data: str) -> "LearningJourney":
        return cls.from_dict(json.loads(data))


def demo() -> None:
    j = LearningJourney(topic="limits", sub_concepts=[{"name": "def", "mastery": 0.8, "visited": True}])
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
