"""Tests for Bloom cognitive taxonomy tracking and load-based difficulty regulation."""

from pitagora.teaching.analyzer import (
    BloomLevel,
    CognitiveLoad,
    ResponseAnalyzer,
    ResponseClassification,
)
from pitagora.teaching.session import TeachingSession


def test_analyzer_bloom_and_load_parsing():
    def fake_chat(messages, model=None, config=None):
        return '{"label": "correct", "rationale": "good evaluation", "bloom_level": "evaluate", "cognitive_load": "optimal"}'

    analyzer = ResponseAnalyzer(fake_chat)
    res = analyzer.classify("The Lagrangian formalism eliminates constraint forces.", "Lagrangian", "Intuition")
    assert res.label == "correct"
    assert res.bloom_level == "evaluate"
    assert res.cognitive_load == "optimal"


def test_teaching_session_difficulty_regulation_with_bloom_and_load():
    session = TeachingSession(topic="Variational Calculus", user_level="intermediate")
    initial_diff = session.difficulty_level

    # Evaluating / deeper response increases difficulty
    session.apply_classification(
        classification="correct",
        delta=0.15,
        bloom_level="evaluate",
        cognitive_load="optimal",
    )
    assert session.difficulty_level >= initial_diff

    # Overloaded / confused response decreases difficulty
    session.apply_classification(
        classification="confused",
        delta=-0.2,
        bloom_level="recall",
        cognitive_load="overloaded",
    )
    assert session.difficulty_level <= initial_diff
