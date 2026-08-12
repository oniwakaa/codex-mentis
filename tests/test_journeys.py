"""Tests for Learning Journeys persistence (TASK 3)."""
import json
import tempfile
from pathlib import Path

import pytest

import pitagora.journeys.store as store
from pitagora.journeys.model import LearningJourney, JourneyStatus
from pitagora.journeys.store import (
    save_journey, load_journey, list_journeys, delete_journey, get_or_create_journey,
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
