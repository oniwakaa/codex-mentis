"""Tests for the WS1/WS3a feedback-loop wiring (real quality signal)."""
import os
import tempfile

import pytest

from pitagora.agents.self_improver import (
    SelfImproverAgent, quality_from_classification, CLASSIFICATION_QUALITY,
)
from pitagora.teaching.session import TeachingSession, ALL_STYLES
from tests.conftest import MockProvider
from tests.test_strategy import MockTutor


# ─── quality mapping ─────────────────────────────────────────────────────────

def test_quality_mapping():
    assert quality_from_classification("correct") == 5
    assert quality_from_classification("deeper") == 5
    assert quality_from_classification("partial") == 3
    assert quality_from_classification("confused") == 1
    assert quality_from_classification("off_topic") == 1
    # unknown label → neutral
    assert quality_from_classification("nonsense") == 3
    # all canonical labels covered
    from pitagora.teaching.analyzer import Classification
    for label in Classification:
        assert label.value in CLASSIFICATION_QUALITY


# ─── _seed_session_style ─────────────────────────────────────────────────────

def test_seed_session_style_no_data():
    """With <5 interactions, the session keeps its default style."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        improver = SelfImproverAgent(MockProvider(), db_path=db_path)
        session = TeachingSession("calculus", ["limits"])
        original = session.current_style
        from pitagora.chat import _seed_session_style
        _seed_session_style(session, improver)
        assert session.current_style == original
    finally:
        os.unlink(db_path)


def test_seed_session_style_with_data():
    """With ≥5 interactions, the session style is seeded from cross-session metrics."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        improver = SelfImproverAgent(MockProvider(), db_path=db_path)
        # Record 6 successful socratic interactions for "calculus"
        for _ in range(6):
            improver.record_interaction("calculus", "intermediate", "socratic", 5)
        # Record 2 failed formal interactions
        for _ in range(2):
            improver.record_interaction("calculus", "intermediate", "formal", 1)
        session = TeachingSession("calculus", ["limits"])
        from pitagora.chat import _seed_session_style
        _seed_session_style(session, improver)
        # socratic should win (higher avg quality)
        assert session.current_style == "socratic"
        assert session.current_style in ALL_STYLES
    finally:
        os.unlink(db_path)


def test_seed_session_style_none_improver():
    """No improver → no crash, no change."""
    session = TeachingSession("calculus", ["limits"])
    original = session.current_style
    from pitagora.chat import _seed_session_style
    _seed_session_style(session, None)
    assert session.current_style == original


# ─── _build_feedback_loop ────────────────────────────────────────────────────

def test_build_feedback_loop():
    """Best-effort construction returns the three components (or None)."""
    from pitagora.chat import _build_feedback_loop
    improver, skill_evo, skills_engine = _build_feedback_loop()
    # In a working environment, all three should be built.
    if improver is not None:
        assert hasattr(improver, "record_interaction")
    if skill_evo is not None:
        assert hasattr(skill_evo, "record_use")
    if skills_engine is not None:
        assert hasattr(skills_engine, "match_skills")


# ─── _run_teaching_turn records real quality ────────────────────────────────

class _FakeAnalyzer:
    """Analyzer stub that returns a fixed classification."""
    def __init__(self, label, delta):
        self._label = label
        self._delta = delta

    def classify(self, reply, topic, sub_concept, config=None, model=None):
        from pitagora.teaching.analyzer import ResponseClassification
        return ResponseClassification(label=self._label, delta=self._delta,
                                      rationale="stub", via_shortcut=False)


def test_teaching_turn_records_real_quality():
    """A controller teaching turn feeds the improver with quality derived
    from the learner's classified reply (correct → quality 5)."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        improver = SelfImproverAgent(MockProvider(), db_path=db_path)
        from pitagora.skills.evolution import SkillEvolution
        from pitagora.skills.engine import SkillsEngine
        skill_evo = SkillEvolution()
        skills_engine = SkillsEngine()

        session = TeachingSession("algebra", ["quadratic formula"])
        analyzer = _FakeAnalyzer("correct", 0.15)

        from pitagora.chat_controller import ChatController
        controller = ChatController(
            mode="study",
            topic="algebra",
            config={"default_model": "m"},
            completion=lambda messages, model=None, config=None: "ok",
            rag_lookup=lambda query: "",
            concept_lookup=lambda topic: "",
            verify_math=lambda response: None,
            save_memory=lambda role, content, topic: None,
            record_study=lambda topic, user_input: None,
            due_reviews=lambda: None,
            user_context="",
            feedback_loop=(improver, skill_evo, skills_engine),
        )
        controller.teaching_session = session
        controller.teaching_analyzer = analyzer

        # Drive one teaching turn through the controller (headless, no console).
        list(controller.handle_input("I solved it"))

        # The improver should have recorded a quality-5 interaction (correct → 5)
        report = improver.strategy_report(topic="algebra")
        assert any(r["uses"] >= 1 for r in report)
        # Find the recorded strategy and check avg_quality
        for r in report:
            if r["uses"] >= 1:
                assert r["avg_quality"] == 5.0  # correct → quality 5
    finally:
        os.unlink(db_path)


# ─── rate_explanation (orchestrator one-shot path) ───────────────────────────

@pytest.mark.asyncio
async def test_rate_explanation_parses_digit():
    """rate_explanation returns the integer the LLM emits."""
    improver = SelfImproverAgent(MockProvider())
    improver.provider.responses.append({"content": "4", "tool_calls": []})
    q = await improver.rate_explanation("limits", "beginner", "socratic", "A clear intro.")
    assert q == 4


@pytest.mark.asyncio
async def test_rate_explanation_parses_embedded_digit():
    """rate_explanation finds the integer in a longer response."""
    improver = SelfImproverAgent(MockProvider())
    improver.provider.responses.append({"content": "Rating: 5", "tool_calls": []})
    q = await improver.rate_explanation("limits", "beginner", "socratic", "Great.")
    assert q == 5


@pytest.mark.asyncio
async def test_rate_explanation_fallback_no_digit():
    """No digit in the response → neutral 3."""
    improver = SelfImproverAgent(MockProvider())
    # default MockProvider response has no 1-5 digit
    q = await improver.rate_explanation("limits", "beginner", "socratic", "Some text.")
    assert q == 3


@pytest.mark.asyncio
async def test_rate_explanation_empty():
    """Empty explanation → neutral 3 without an LLM call."""
    improver = SelfImproverAgent(MockProvider())
    q = await improver.rate_explanation("limits", "beginner", "socratic", "")
    assert q == 3


@pytest.mark.asyncio
async def test_rate_explanation_rejects_out_of_range():
    """An out-of-range digit (7) is ignored → neutral 3."""
    improver = SelfImproverAgent(MockProvider())
    improver.provider.responses.append({"content": "7", "tool_calls": []})
    q = await improver.rate_explanation("limits", "beginner", "socratic", "x")
    assert q == 3


def test_orchestrator_records_rated_quality():
    """The orchestrator one-shot tutor path records the LLM-rated quality."""
    import tempfile, os
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        improver = SelfImproverAgent(MockProvider(), db_path=db_path)
        # rate_explanation will pop this → quality 5
        improver.provider.responses.append({"content": "5", "tool_calls": []})
        from pitagora.agents.orchestrator import Orchestrator
        orch = Orchestrator(agents={"tutor": MockTutor()}, self_improver=improver)
        resp = orch.process("Explain calculus", mode="study")
        assert resp.content.startswith("athink")
        report = improver.strategy_report()
        # The recorded quality should be 5 (from rate_explanation), not 3.
        for r in report:
            if r["uses"] >= 1:
                assert r["avg_quality"] == 5.0
                break
        else:
            assert False, "no interaction recorded"
    finally:
        os.unlink(db_path)
