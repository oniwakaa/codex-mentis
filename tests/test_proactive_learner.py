"""Tests for ProactiveLearner module."""

from unittest.mock import MagicMock
from pitagora.concepts.graph import ConceptGraph
from pitagora.concepts.tracker import MasteryTracker
from pitagora.knowledge.proactive import ProactiveLearner
from pitagora.memory.spaced_repetition import SpacedRepetition


def test_proactive_diagnosis_roots_and_zpd():
    cg = ConceptGraph()
    tracker = MasteryTracker(concept_graph=cg)
    spaced_rep = MagicMock(spec=SpacedRepetition)
    spaced_rep.get_due_reviews.return_value = []

    learner = ProactiveLearner(
        concept_graph=cg,
        mastery_tracker=tracker,
        spaced_rep=spaced_rep,
    )

    diag = learner.diagnose()
    assert diag.mastered_count == 0
    assert diag.recommended_topic is not None
    assert len(diag.zpd_candidates) > 0


def test_proactive_diagnosis_with_due_cards():
    cg = ConceptGraph()
    tracker = MasteryTracker(concept_graph=cg)
    spaced_rep = MagicMock(spec=SpacedRepetition)
    spaced_rep.get_due_reviews.return_value = [
        {"concept": "calc_limits", "interval": 1}
    ]

    learner = ProactiveLearner(
        concept_graph=cg,
        mastery_tracker=tracker,
        spaced_rep=spaced_rep,
    )

    diag = learner.diagnose()
    assert diag.due_reviews == ["calc_limits"]
    assert diag.recommended_topic == "calc_limits"
    assert "due for spaced repetition" in diag.recommended_reason


def test_proactive_study_context_preparation():
    cg = ConceptGraph()
    acq = MagicMock()
    acq.search_papers.return_value = [
        {"title": "Lagrangian Mechanics Primer", "url": "https://arxiv.org/abs/1234.5678", "snippet": "A pedagogical introduction"}
    ]

    learner = ProactiveLearner(
        concept_graph=cg,
        knowledge_acq=acq,
    )

    ctx = learner.prepare_study_context("mech_lagrangian", auto_fetch=True)
    assert ctx["topic"] == "mech_lagrangian"
    assert len(ctx["sources"]) == 1
    assert ctx["sources"][0]["title"] == "Lagrangian Mechanics Primer"
