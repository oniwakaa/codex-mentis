"""Tests for the Teaching Session Engine (TASK 2)."""
import pytest

from pitagora.teaching.session import (
    TeachingSession, TeachingState, StyleEffectiveness, SubConcept, SHORTCUTS,
)


def test_initial_state():
    s = TeachingSession("limits", ["def", "epsilon-delta"])
    assert s.state == TeachingState.introducing
    assert s.comprehension_score == 0.0
    assert s.current_index == 0
    assert s.current_subconcept.name == "def"
    assert s.interaction_count == 0


def test_state_transitions():
    s = TeachingSession("limits", ["a", "b"])
    s.transition(TeachingState.exploring)
    assert s.state == TeachingState.exploring
    s.transition(TeachingState.checking)
    assert s.state == TeachingState.checking
    s.transition(TeachingState.paused)
    assert s.state == TeachingState.paused
    # resume restores prior (checking)
    s.resume()
    assert s.state == TeachingState.checking


def test_pause_resume():
    s = TeachingSession("t", ["a"])
    s.transition(TeachingState.exploring)
    s.pause()
    assert s.state == TeachingState.paused
    s.resume()
    assert s.state == TeachingState.exploring


def test_comprehension_tracking_and_clamp():
    s = TeachingSession("t", ["a"])
    s.apply_classification("correct", 0.15, style="feynman")
    assert 0 < s.comprehension_score <= 0.15
    # Negative delta clamps to 0
    s.apply_classification("confused", -0.5, style="feynman")
    assert s.comprehension_score >= 0.0
    # Large positive clamps to 1.0
    s.comprehension_score = 0.95
    s.apply_classification("correct", 0.5, style="feynman")
    assert s.comprehension_score <= 1.0


def test_style_effectiveness_records_best():
    se = StyleEffectiveness()
    se.record("feynman", 0.15)
    se.record("feynman", 0.15)
    se.record("formal", -0.2)
    assert se.attempts["feynman"] == 2
    assert se.success["feynman"] == 1.0
    assert se.success["formal"] == 0.0
    assert se.best() == "feynman"


def test_shortcuts_parse():
    assert TeachingSession.is_shortcut("n")
    assert TeachingSession.is_shortcut("?")
    assert not TeachingSession.is_shortcut("hello world")
    assert TeachingSession.shortcut_action("d") == "go_deeper"
    assert TeachingSession.shortcut_action("p") == "pause"


def test_handle_shortcut_pause_resume():
    s = TeachingSession("t", ["a"])
    s.transition(TeachingState.exploring)
    assert s.handle_shortcut("p") == "pause"
    assert s.state == TeachingState.paused
    assert s.handle_shortcut("r") == "resume"
    assert s.state == TeachingState.exploring
    assert s.handle_shortcut("hello") is None


def test_next_action_correct_advances():
    s = TeachingSession("t", ["a", "b", "c"])
    s.transition(TeachingState.checking)
    # correct in checking → advance to next sub-concept
    action = s.next_action("correct")
    assert action == "advance"
    assert s.current_index == 1
    # last sub-concept correct → review
    s.current_index = 2
    s.transition(TeachingState.checking)
    action = s.next_action("correct")
    assert action == "review"
    assert s.state == TeachingState.reviewing


def test_next_action_confused_adapts():
    s = TeachingSession("t", ["a"])
    s.transition(TeachingState.exploring)
    assert s.next_action("confused") == "adapt"
    assert s.next_action("off_topic") == "adapt"
    assert s.next_action("question") == "adapt"
    assert s.next_action("deeper") == "adapt"


def test_next_action_skip_advances():
    s = TeachingSession("t", ["a", "b"])
    s.transition(TeachingState.exploring)
    assert s.next_action("skip") == "advance"
    assert s.current_index == 1


def test_save_load_round_trip():
    s = TeachingSession("limits", ["def", "epsilon-delta"], user_level="advanced")
    s.transition(TeachingState.exploring)
    s.apply_classification("correct", 0.15, style="feynman")
    s.apply_classification("partial", 0.05, style="formal")
    blob = s.to_json()
    s2 = TeachingSession.from_json(blob)
    assert s2.topic == "limits"
    assert s2.user_level == "advanced"
    assert s2.state == TeachingState.exploring
    assert s2.comprehension_score == s.comprehension_score
    assert s2.current_index == s.current_index
    assert s2.sub_concepts[0].name == "def"
    assert s2.sub_concepts[0].visited is True
    assert s2.style_effectiveness.attempts["feynman"] == 1
    assert s2.interaction_count == 2


def test_set_sub_concepts_replaces():
    s = TeachingSession("t", [])
    assert s.current_subconcept is None
    s.set_sub_concepts(["x", "y"])
    assert len(s.sub_concepts) == 2
    assert s.current_subconcept.name == "x"


def test_subconcept_visited_and_mastery_on_apply():
    s = TeachingSession("t", ["a"])
    s.apply_classification("correct", 0.15, style="feynman")
    sc = s.sub_concepts[0]
    assert sc.visited is True
    assert sc.mastery > 0.0
