"""Tests for Feynman Teach-Back reverse-tutoring module."""

from pitagora.teaching.feynman import FeynmanSession, FeynmanRubric, FeynmanEvaluation
from pitagora.memory.store import MemoryStore
from pitagora.memory.spaced_repetition import SpacedRepetition


def test_feynman_rubric_overall():
    rubric = FeynmanRubric(clarity=0.8, precision=0.9, analogy=0.7, depth=0.6)
    expected = 0.30 * 0.8 + 0.30 * 0.9 + 0.20 * 0.7 + 0.20 * 0.6
    assert abs(rubric.overall - expected) < 1e-5


def test_feynman_session_heuristic_turn(tmp_path):
    db_path = str(tmp_path / "test_feynman.db")
    mem = MemoryStore(db_path=db_path)
    sr = SpacedRepetition(db_path=db_path)

    session = FeynmanSession(
        concept="Entropy",
        domain="Physics",
        chat_completion_fn=None,  # Fallback mode
        memory_store=mem,
        spaced_repetition=sr,
    )

    explanation = "Entropy is like a measure of disorder in a closed room. For example, imagine gas molecules spreading out."
    evaluation = session.evaluate_explanation(explanation)

    assert isinstance(evaluation, FeynmanEvaluation)
    assert evaluation.rubric.analogy >= 0.8
    assert len(session.evaluations) == 1

    report = session.generate_final_report()
    assert report["concept"] == "Entropy"
    assert report["turns_completed"] == 1
    assert "overall_score" in report


def test_feynman_session_with_mock_llm(tmp_path):
    db_path = str(tmp_path / "test_feynman_llm.db")
    mem = MemoryStore(db_path=db_path)
    sr = SpacedRepetition(db_path=db_path)

    def mock_chat(messages, **kwargs):
        return '''{
            "clarity": 0.9,
            "precision": 0.85,
            "analogy": 0.95,
            "depth": 0.8,
            "jargon_used": ["microstates"],
            "misconceptions": ["disorder equals messiness"],
            "strengths": ["great coin toss analogy"],
            "student_question": "Why do microstates always tend to higher probability distributions?",
            "is_mastered": true,
            "feedback_summary": "Superb intuitive clarity."
        }'''

    session = FeynmanSession(
        concept="Second Law of Thermodynamics",
        domain="Physics",
        chat_completion_fn=mock_chat,
        memory_store=mem,
        spaced_repetition=sr,
    )

    eval_res = session.evaluate_explanation("It is all about the count of microstates, like flipping 100 coins.")
    assert eval_res.is_mastered is True
    assert eval_res.rubric.clarity == 0.9
    assert "microstates" in eval_res.jargon_used
    assert "disorder equals messiness" in eval_res.misconceptions

    # Check that misconception was auto-persisted in memory
    misconceptions = mem.get_misconceptions(topic="Physics", concept="Second Law of Thermodynamics")
    assert len(misconceptions) == 1
    assert misconceptions[0]["misconception"] == "disorder equals messiness"

    # Check that review card was scheduled
    card_metrics = sr.get_review_metrics("Second Law of Thermodynamics: disorder equals messiness")
    assert card_metrics["interval"] == 1
    assert card_metrics["next_review"] is not None
