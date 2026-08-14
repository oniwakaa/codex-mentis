"""Tests for WS1: strategy CLI + orchestrator feedback-loop wiring."""

import pytest
from typer.testing import CliRunner

from pitagora.agents.base import AgentResponse
from pitagora.agents.orchestrator import Orchestrator
from pitagora.agents.self_improver import SelfImproverAgent
from pitagora.cli.app import app
from tests.conftest import MockProvider

runner = CliRunner()


# ─── Strategy CLI ───────────────────────────────────────────────────────────


def test_strategy_help_lists_subcommands():
    result = runner.invoke(app, ["strategy", "--help"])
    assert result.exit_code == 0
    assert "report" in result.output
    assert "digest" in result.output


def test_strategy_report_empty():
    """report with no data should exit cleanly."""
    result = runner.invoke(app, ["strategy", "report"])
    assert result.exit_code == 0


def test_strategy_digest_empty():
    """digest with no data should exit cleanly."""
    result = runner.invoke(app, ["strategy", "digest"])
    assert result.exit_code == 0


def test_strategy_help_top_level():
    """The top-level --help should now list the strategy group."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "strategy" in result.output


# ─── Orchestrator wiring ────────────────────────────────────────────────────


class MockTutor:
    name = "Tutor"
    role = "tutor"
    tools: list = []

    async def explain_concept(self, topic, level="beginner"):
        return AgentResponse(content=f"explain {topic}", tool_calls=[], confidence=0.9, metadata={})

    async def athink(self, prompt, context=None):
        return AgentResponse(content=f"athink {prompt}", tool_calls=[], confidence=0.9, metadata={})


def test_orchestrator_without_self_improver_unchanged():
    """No self_improver → existing behavior (explain_concept path)."""
    orch = Orchestrator(agents={"tutor": MockTutor()})
    resp = orch.process("Explain calculus", mode="study")
    assert resp.content.startswith("explain")


def test_orchestrator_with_self_improver_records_interaction():
    """With a self_improver, tutor dispatch records an interaction in the metrics DB."""
    improver = SelfImproverAgent(MockProvider(), db_path=":memory:")
    # In-memory DB won't persist across connections; use a temp file instead.
    import os
    import tempfile

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        improver = SelfImproverAgent(MockProvider(), db_path=db_path)
        orch = Orchestrator(agents={"tutor": MockTutor()}, self_improver=improver)
        resp = orch.process("Explain calculus", mode="study")
        # Strategy-injected path uses athink, so content starts with "athink"
        assert resp.content.startswith("athink")
        # And the interaction was recorded
        report = improver.strategy_report()
        assert any(r["uses"] >= 1 for r in report)
    finally:
        os.unlink(db_path)
