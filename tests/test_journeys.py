"""Tests for Learning Journeys persistence (TASK 3)."""

from datetime import datetime

import pytest

from pitagora.journeys import store
from pitagora.journeys.model import JourneyStatus, LearningJourney
from pitagora.journeys.store import (
    delete_journey,
    get_or_create_journey,
    list_journeys,
    load_journey,
    save_journey,
)


@pytest.fixture(autouse=True)
def tmp_journeys_dir(tmp_path, monkeypatch):
    """Redirect the store's JOURNEYS_DIR to a temp dir for each test."""
    tmp = tmp_path / "journeys"
    monkeypatch.setattr(store, "JOURNEYS_DIR", tmp)
    return tmp


def test_save_and_load_round_trip(tmp_journeys_dir):
    j = LearningJourney(
        topic="limits",
        sub_concepts=[{"name": "def", "mastery": 0.8, "visited": True}],
        interaction_count=3,
        comprehension_history=[0.1, 0.25, 0.4],
    )
    jid = save_journey(j)
    assert (tmp_journeys_dir / f"{jid}.json").exists()
    loaded = load_journey(jid)
    assert loaded is not None
    assert loaded.topic == "limits"
    assert loaded.interaction_count == 3
    assert loaded.sub_concepts[0]["name"] == "def"


def test_load_missing_returns_none():
    assert load_journey("does-not-exist") is None


def test_list_journeys_empty(tmp_journeys_dir):
    assert list_journeys() == []


def test_list_journeys_newest_first(tmp_journeys_dir):
    j1 = LearningJourney(topic="a")
    save_journey(j1)
    j2 = LearningJourney(topic="b")
    save_journey(j2)
    listed = list_journeys()
    assert len(listed) == 2
    # Most recently saved (updated_at later) comes first.
    assert listed[0]["topic"] == "b"
    assert listed[1]["topic"] == "a"


def test_delete_journey(tmp_journeys_dir):
    j = LearningJourney(topic="x")
    jid = save_journey(j)
    assert delete_journey(jid) is True
    assert load_journey(jid) is None
    assert delete_journey(jid) is False


def test_get_or_create_creates_new(tmp_journeys_dir):
    j = get_or_create_journey("limits", ["def", "eps-delta"])
    assert j.topic == "limits"
    assert len(j.sub_concepts) == 2
    assert j.status == JourneyStatus.active.value
    jid = save_journey(j)
    # second call resumes the same journey
    j2 = get_or_create_journey("limits", ["def", "eps-delta"])
    assert j2.id == jid


def test_get_or_create_resumes_paused(tmp_journeys_dir):
    j = get_or_create_journey("limits", ["def"])
    jid = save_journey(j)
    j.status = JourneyStatus.paused.value
    save_journey(j)
    j2 = get_or_create_journey("limits")
    assert j2.id == jid
    assert j2.status == JourneyStatus.active.value


def test_journey_serialization_round_trip():
    j = LearningJourney(topic="t", interaction_count=5)
    blob = j.to_json()
    j2 = LearningJourney.from_json(blob)
    assert j2.topic == "t"
    assert j2.id == j.id
    assert j2.interaction_count == 5


def test_journey_from_dict_ignores_unknown_keys():
    j = LearningJourney.from_dict({"topic": "t", "unknown_key": 42})
    assert j.topic == "t"


def test_rejects_path_traversal_ids(tmp_journeys_dir):
    outside = tmp_journeys_dir.parent / "outside.json"
    outside.write_text('{"topic": "private"}')

    assert load_journey("../outside") is None
    assert delete_journey("../outside") is False
    assert outside.exists()

    with pytest.raises(ValueError):
        save_journey(LearningJourney(topic="x", id="../outside"))


def test_save_is_atomic_when_replace_fails(tmp_journeys_dir, monkeypatch):
    journey = LearningJourney(topic="original", id="atomic-test")
    save_journey(journey)
    path = tmp_journeys_dir / "atomic-test.json"
    original = path.read_text()
    journey.topic = "updated"

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(store.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failure"):
        save_journey(journey)

    assert path.read_text() == original
    assert not list(tmp_journeys_dir.glob("*.tmp"))


def test_malformed_journey_files_are_ignored(tmp_journeys_dir):
    tmp_journeys_dir.mkdir()
    (tmp_journeys_dir / "broken.json").write_text("{not json")
    (tmp_journeys_dir / "array.json").write_text("[]")
    (tmp_journeys_dir / "missing-topic.json").write_text('{"id": "missing-topic"}')

    assert load_journey("broken") is None
    assert load_journey("array") is None
    assert load_journey("missing-topic") is None
    assert list_journeys() == []


def test_filename_is_authoritative_over_stored_id(tmp_journeys_dir):
    tmp_journeys_dir.mkdir()
    (tmp_journeys_dir / "safe-id.json").write_text(
        '{"id": "../outside", "topic": "limits", "updated_at": "2024-01-01T00:00:00Z"}'
    )

    loaded = load_journey("safe-id")

    assert loaded is not None
    assert loaded.id == "safe-id"
    assert list_journeys()[0]["id"] == "safe-id"


def test_journey_timestamps_are_timezone_aware():
    journey = LearningJourney(topic="t")
    assert datetime.fromisoformat(journey.created_at).tzinfo is not None
    assert datetime.fromisoformat(journey.updated_at).tzinfo is not None


def test_loads_legacy_journey_field_names():
    journey = LearningJourney.from_dict(
        {
            "id": "legacy-id",
            "topic": "limits",
            "started_at": "2024-01-01T00:00:00",
            "last_active": "2024-01-02T00:00:00",
            "total_interactions": 7,
            "unknown_key": "ignored",
        }
    )

    assert journey.created_at == "2024-01-01T00:00:00+00:00"
    assert journey.updated_at == "2024-01-02T00:00:00+00:00"
    assert journey.interaction_count == 7


def test_markdown_export_is_direct_and_readable():
    journey = LearningJourney(
        topic="Limits",
        sub_concepts=[{"name": "Definition", "mastery": 0.8, "visited": True}],
    )

    markdown = journey.to_markdown()

    assert markdown.startswith("# Learning Journey: Limits")
    assert "Definition" in markdown
    assert "80%" in markdown
