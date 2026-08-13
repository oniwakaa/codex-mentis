"""Tests for the WS1/WS3a feedback-loop wiring (real quality signal)."""
import os
import tempfile

import pytest

from pitagora.agents.self_improver import (
    SelfImproverAgent, quality_from_classification, CLASSIFICATION_QUALITY,
)
from pitagora.teaching.session import TeachingSession, ALL_STYLES
from tests.conftest import MockProvider


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
    """_run_teaching_turn feeds the improver with quality derived from the label."""
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

        from pitagora.chat import _run_teaching_turn
        from rich.console import Console
        console = Console(record=True, width=80)

        _run_teaching_turn(
            console, session, analyzer, "I solved it", {}, "m", [],
            improver=improver, skill_evo=skill_evo, skills_engine=skills_engine,
        )

        # The improver should have recorded a quality-5 interaction (correct → 5)
        report = improver.strategy_report(topic="algebra")
        assert any(r["uses"] >= 1 for r in report)
        # Find the recorded strategy and check avg_quality
        for r in report:
            if r["uses"] >= 1:
                assert r["avg_quality"] == 5.0  # correct → quality 5
    finally:
        os.unlink(db_path)
