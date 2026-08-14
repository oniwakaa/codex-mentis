"""Tests for the Teaching Session Engine (TASK 2)."""

from datetime import datetime

from pitagora.teaching.session import (
    ALL_STYLES,
    StyleEffectiveness,
    TeachingSession,
    TeachingState,
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


def test_paused_session_round_trip_resumes_exact_state():
    session = TeachingSession("t", ["a"])
    session.transition(TeachingState.checking)
    session.pause()

    restored = TeachingSession.from_json(session.to_json())

    assert restored.state == TeachingState.paused
    restored.resume()
    assert restored.state == TeachingState.checking


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


def test_all_six_styles_survive_serialization():
    assert ALL_STYLES == (
        "feynman",
        "formal",
        "visual",
        "historical",
        "socratic",
        "applied",
    )
    restored = StyleEffectiveness.from_dict(StyleEffectiveness().to_dict())
    assert tuple(restored.attempts) == ALL_STYLES
    assert tuple(restored.success) == ALL_STYLES


def test_different_style_rejects_current_style():
    session = TeachingSession("t", ["a"])
    session.apply_classification("correct", 0.15, style="feynman")
    assert session.style_effectiveness.best() == "feynman"

    session.apply_classification("different_style", 0.0, style="feynman")

    assert session.next_action("different_style") == "adapt"
    assert session.style_effectiveness.best() == "formal"


def test_explicit_signals_regulate_difficulty_within_zpd_bounds():
    session = TeachingSession("t", ["a"], user_level="intermediate")
    assert session.difficulty_level == 3

    for _ in range(10):
        session.apply_classification("deeper", 0.05)
    assert session.difficulty_level == 5

    for _ in range(10):
        session.apply_classification("confused", -0.2)
    assert session.difficulty_level == 1

    restored = TeachingSession.from_json(session.to_json())
    assert restored.difficulty_level == 1


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


def test_visualize_quiz_review_and_completed_states_are_reachable():
    session = TeachingSession("t", ["a"])
    session.transition(TeachingState.exploring)

    assert session.next_action("visualize") == "visualize"
    session.transition(TeachingState.visualizing)
    assert session.next_action("quiz") == "quiz"
    session.transition(TeachingState.quizzing)
    assert session.next_action("correct") == "check"

    session.transition(TeachingState.checking)
    assert session.next_action("correct") == "review"
    assert session.state == TeachingState.reviewing
    assert session.next_action("skip") == "complete"

    session.complete()
    assert session.next_action("correct") == "complete"


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


def test_session_timestamps_are_timezone_aware():
    session = TeachingSession("t")
    assert datetime.fromisoformat(session.created_at).tzinfo is not None
    assert datetime.fromisoformat(session.updated_at).tzinfo is not None


def test_loads_legacy_session_field_names():
    restored = TeachingSession.from_dict(
        {
            "topic": "limits",
            "state": "paused",
            "sub_concepts": [
                {
                    "name": "definition",
                    "mastery_score": 0.7,
                    "status": "active",
                }
            ],
            "current_sub_concept_idx": 0,
            "style_effectiveness": {"visual": 0.75},
            "preferred_style": "visual",
            "interaction_history": [{"state": "checking"}],
            "total_interactions": 4,
            "last_active": "2024-01-01T00:00:00",
        }
    )

    assert restored.current_index == 0
    assert restored.sub_concepts[0].mastery == 0.7
    assert restored.style_effectiveness.success["visual"] == 0.75
    assert restored.current_style == "visual"
    assert restored.interaction_count == 4
    restored.resume()
    assert restored.state == TeachingState.checking
