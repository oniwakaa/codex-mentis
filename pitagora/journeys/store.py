"""Journey store — save/load/list/delete LearningJourney JSON files.

Lives in ~/.pitagora/journeys/. One file per journey, named <id>.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from pitagora.core.constants import JOURNEYS_DIR
from pitagora.journeys.model import JourneyStatus, LearningJourney

logger = logging.getLogger(__name__)
_VALID_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


def _ensure_dir() -> None:
    JOURNEYS_DIR.mkdir(parents=True, exist_ok=True)


def _path(jid: str) -> Path:
    if not isinstance(jid, str) or _VALID_ID.fullmatch(jid) is None:
        raise ValueError("invalid journey id")
    return JOURNEYS_DIR / f"{jid}.json"


def save_journey(journey: LearningJourney) -> str:
    """Persist (or update) a journey. Returns the journey id."""
    _ensure_dir()
    path = _path(journey.id)
    journey.touch()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{journey.id}.",
        suffix=".tmp",
        dir=JOURNEYS_DIR,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(journey.to_dict(), file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return journey.id


def load_journey(jid: str) -> LearningJourney | None:
    try:
        p = _path(jid)
    except ValueError:
        return None
    if not p.is_file() or p.is_symlink():
        return None
    try:
        with p.open(encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise TypeError("journey file must contain an object")
        data["id"] = jid
        return LearningJourney.from_dict(data)
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as e:
        logger.warning("failed to load journey %s: %s", jid, e)
        return None


def list_journeys() -> list[dict[str, Any]]:
    """Return summary dicts for all stored journeys, newest first."""
    if not JOURNEYS_DIR.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in JOURNEYS_DIR.glob("*.json"):
        journey = load_journey(p.stem)
        if journey is None:
            continue
        out.append(
            {
                "id": p.stem,
                "topic": journey.topic,
                "status": journey.status,
                "interaction_count": journey.interaction_count,
                "updated_at": journey.updated_at,
                "sub_concepts": journey.sub_concepts,
            }
        )
    out.sort(key=lambda j: j.get("updated_at", ""), reverse=True)
    return out


def delete_journey(jid: str) -> bool:
    try:
        p = _path(jid)
    except ValueError:
        return False
    if p.exists():
        p.unlink()
        return True
    return False


def get_or_create_journey(topic: str, sub_concepts: list[str] | None = None) -> LearningJourney:
    """Return the most recent active journey for `topic`, or create one.

    Used by /explore so re-exploring a topic resumes its journey instead of
    starting fresh every time.
    """
    for summary in list_journeys():
        if summary.get("topic") == topic and summary.get("status") in (
            JourneyStatus.active.value,
            JourneyStatus.paused.value,
        ):
            loaded = load_journey(summary["id"])
            if loaded is not None:
                loaded.status = JourneyStatus.active.value
                return loaded
    subs = [{"name": n, "mastery": 0.0, "visited": False} for n in (sub_concepts or [])]
    return LearningJourney(topic=topic, sub_concepts=subs)


def demo() -> None:
    """Self-check: save/load/list/delete round-trip against a temp dir."""
    import tempfile
    from pathlib import Path

    from pitagora.journeys import store

    # Redirect JOURNEYS_DIR to a temp location for this check.
    orig = store.JOURNEYS_DIR
    tmp = Path(tempfile.mkdtemp()) / "journeys"
    store.JOURNEYS_DIR = tmp
    try:
        j = LearningJourney(
            topic="test_topic", sub_concepts=[{"name": "a", "mastery": 0.0, "visited": False}]
        )
        jid = save_journey(j)
        assert load_journey(jid).topic == "test_topic"
        all_j = list_journeys()
        assert len(all_j) == 1 and all_j[0]["id"] == jid
        g = get_or_create_journey("test_topic", ["a"])
        assert g.id == jid  # resumed, not recreated
        g2 = get_or_create_journey("other", ["x"])
        assert g2.id != jid
        assert delete_journey(jid) is True
        assert load_journey(jid) is None
        print("journey store demo ok")
    finally:
        store.JOURNEYS_DIR = orig


if __name__ == "__main__":
    demo()
