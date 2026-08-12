"""Journey store — save/load/list/delete LearningJourney JSON files.

Lives in ~/.pitagora/journeys/. One file per journey, named <id>.json.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from pitagora.core.constants import JOURNEYS_DIR
from pitagora.journeys.model import LearningJourney, JourneyStatus

logger = logging.getLogger(__name__)


def _ensure_dir() -> None:
    JOURNEYS_DIR.mkdir(parents=True, exist_ok=True)


def _path(jid: str) -> Any:
    return JOURNEYS_DIR / f"{jid}.json"


def save_journey(journey: LearningJourney) -> str:
    """Persist (or update) a journey. Returns the journey id."""
    _ensure_dir()
    journey.touch()
    with open(_path(journey.id), "w") as f:
        json.dump(journey.to_dict(), f, indent=2)
    return journey.id


def load_journey(jid: str) -> Optional[LearningJourney]:
    p = _path(jid)
    if not p.exists():
        return None
    try:
        with open(p) as f:
            return LearningJourney.from_dict(json.load(f))
    except Exception as e:
        logger.warning("failed to load journey %s: %s", jid, e)
        return None


def list_journeys() -> List[Dict[str, Any]]:
    """Return summary dicts for all stored journeys, newest first."""
    if not JOURNEYS_DIR.exists():
        return []
    out: List[Dict[str, Any]] = []
    for p in JOURNEYS_DIR.glob("*.json"):
        try:
            with open(p) as f:
                d = json.load(f)
            out.append({
                "id": d.get("id", p.stem),
                "topic": d.get("topic", "?"),
                "status": d.get("status", "?"),
                "interaction_count": d.get("interaction_count", 0),
                "updated_at": d.get("updated_at", ""),
                "sub_concepts": d.get("sub_concepts", []),
            })
        except Exception:
            continue
    out.sort(key=lambda j: j.get("updated_at", ""), reverse=True)
    return out


def delete_journey(jid: str) -> bool:
    p = _path(jid)
    if p.exists():
        p.unlink()
        return True
    return False


def get_or_create_journey(topic: str, sub_concepts: Optional[List[str]] = None) -> LearningJourney:
    """Return the most recent active journey for `topic`, or create one.

    Used by /explore so re-exploring a topic resumes its journey instead of
    starting fresh every time.
    """
    for summary in list_journeys():
        if summary.get("topic") == topic and summary.get("status") in (
            JourneyStatus.active.value, JourneyStatus.paused.value,
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
    import pitagora.journeys.store as store
    # Redirect JOURNEYS_DIR to a temp location for this check.
    orig = store.JOURNEYS_DIR
    tmp = Path(tempfile.mkdtemp()) / "journeys"
    store.JOURNEYS_DIR = tmp
    try:
        j = LearningJourney(topic="test_topic", sub_concepts=[{"name": "a", "mastery": 0.0, "visited": False}])
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
