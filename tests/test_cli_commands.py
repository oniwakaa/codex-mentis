"""Tests for the doctor and review commands."""
import pytest
from typer.testing import CliRunner
from pitagora.cli.app import app

runner = CliRunner()


def test_doctor_command():
    """Test that the doctor command runs and produces health check output."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Health Check" in result.output or "health" in result.output.lower()
    # Should mention Python version
    assert "Python" in result.output or "python" in result.output.lower()


def test_review_status():
    """Test that review status command runs without error."""
    result = runner.invoke(app, ["review", "status"])
    assert result.exit_code == 0
    # Should show some kind of status
    assert "review" in result.output.lower() or "card" in result.output.lower() or "due" in result.output.lower()


def test_help_shows_all_commands():
    """Test that --help lists all major command groups."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Check for key commands
    for cmd in ["study", "explore", "derive", "verify", "plot", "research", "explain", "debate", "chat"]:
        assert cmd in result.output, f"Command '{cmd}' not found in help output"
    # Check for command groups
    for group in ["concept", "memory", "kb", "config", "skills", "review", "doctor"]:
        assert group in result.output, f"Command group '{group}' not found in help output"


def test_study_help():
    """Test study command help."""
    result = runner.invoke(app, ["study", "--help"])
    assert result.exit_code == 0
    assert "study" in result.output.lower() or "tutor" in result.output.lower()


def test_research_help():
    """Test research command help."""
    result = runner.invoke(app, ["research", "--help"])
    assert result.exit_code == 0
    assert "research" in result.output.lower() or "topic" in result.output.lower()


def test_explain_help():
    """Test explain command help."""
    result = runner.invoke(app, ["explain", "--help"])
    assert result.exit_code == 0
    assert "explain" in result.output.lower() or "level" in result.output.lower()


def test_derive_help():
    """Test derive command help."""
    result = runner.invoke(app, ["derive", "--help"])
    assert result.exit_code == 0


def test_verify_help():
    """Test verify command help."""
    result = runner.invoke(app, ["verify", "--help"])
    assert result.exit_code == 0
