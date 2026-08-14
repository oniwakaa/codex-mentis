import datetime
import math
from unittest.mock import MagicMock

import pytest

from pitagora.concepts.graph import ConceptGraph
from pitagora.concepts.tracker import MasteryTracker


@pytest.fixture
def dummy_graph(temp_yaml):
    return ConceptGraph(yaml_path=temp_yaml)


def test_mastery_tracker_basic_update(temp_db, dummy_graph):
    tracker = MasteryTracker(db_path=temp_db, concept_graph=dummy_graph)

    # Initial mastery is 0
    assert tracker.get_mastery("Calculus") == 0.0

    # Update mastery first time
    tracker.update_mastery("Calculus", 0.8)
    assert tracker.get_mastery("Calculus") == pytest.approx(0.8)

    # Update second time (EMA: 0.8 * 0.75 + 1.0 * 0.25 = 0.60 + 0.25 = 0.85)
    tracker.update_mastery("Calculus", 1.0)
    assert tracker.get_mastery("Calculus", apply_decay=False) == pytest.approx(0.85)


def test_mastery_tracker_decay(temp_db, dummy_graph):
    tracker = MasteryTracker(db_path=temp_db, concept_graph=dummy_graph, decay_rate=0.1)

    # Update mastery
    tracker.update_mastery("Calculus", 1.0)

    # Artificially shift last_updated back by 10 days
    from sqlite_utils import Database

    db = Database(temp_db)
    ten_days_ago = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    db["concept_mastery"].update("Calculus", {"last_updated": ten_days_ago})

    # Decayed score should be 1.0 * exp(-0.1 * 10) = e^-1 = ~0.3678
    decayed = tracker.get_mastery("Calculus", apply_decay=True)
    assert decayed == pytest.approx(math.exp(-1.0), rel=1e-4)


def test_weak_and_strong_areas(temp_db, dummy_graph):
    tracker = MasteryTracker(db_path=temp_db, concept_graph=dummy_graph)

    tracker.update_mastery("Calculus", 0.9)
    tracker.update_mastery("Classical Mechanics", 0.4)

    strong = tracker.get_strong_areas(threshold=0.8)
    weak = tracker.get_weak_areas(threshold=0.5)

    assert len(strong) == 1
    assert strong[0]["concept"] == "Calculus"

    assert len(weak) == 1
    assert weak[0]["concept"] == "Classical Mechanics"


def test_progress_reports(temp_db, dummy_graph):
    tracker = MasteryTracker(db_path=temp_db, concept_graph=dummy_graph)

    tracker.update_mastery("Calculus", 0.9)  # Mastered (>= 0.8)
    tracker.update_mastery("Linear Algebra", 0.5)  # In progress

    report = tracker.get_progress_report()
    assert report["mastered_count"] == 1
    assert "Calculus" in report["mastered_list"]
    assert report["in_progress_count"] == 1
    assert "Linear Algebra" in report["in_progress_list"]
    # Remaining are not started (e.g. Classical Mechanics, Quantum Mechanics)
    assert "Quantum Mechanics" in report["not_started_list"]


def test_assessment_generation(temp_db, dummy_graph):
    tracker = MasteryTracker(db_path=temp_db, concept_graph=dummy_graph)

    assessment = tracker.generate_assessment("Quantum Mechanics", num_questions=3)
    assert assessment["concept"] == "Quantum Mechanics"
    assert len(assessment["questions"]) == 3
    assert assessment["questions"][0]["type"] == "conceptual"
    assert assessment["questions"][1]["type"] == "relational"  # QM has prereqs
