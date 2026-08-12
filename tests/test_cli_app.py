import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
from codex_mentis.cli.app import app
from codex_mentis.agents.base import AgentResponse

@pytest.fixture
def runner():
    return CliRunner()

def test_cli_research_command(runner):
    mock_findings = {
        "total_sources_crawled": 1,
        "findings": ["Finding 1", "Finding 2"],
        "concepts_found": ["Concept A"],
        "sources": [{"title": "Source 1", "url": "https://url1.com"}],
        "citations": [{"title": "Source 1", "url": "https://url1.com"}]
    }
    
    with patch("codex_mentis.knowledge.acquisition.KnowledgeAcquisition.research_topic", return_value=mock_findings):
        result = runner.invoke(app, ["research", "quantum gravity", "--depth", "shallow"])
        assert result.exit_code == 0
        assert "Research Results: quantum gravity" in result.stdout
        assert "Finding 1" in result.stdout

def test_cli_explain_command(runner):
    with patch("codex_mentis.chat.chat_completion", return_value="Feynman explanation text"):
        result = runner.invoke(app, ["explain", "General Relativity", "--level", "beginner"])
        assert result.exit_code == 0
        assert "Feynman explanation text" in result.stdout

def test_cli_debate_command(runner):
    with patch("codex_mentis.chat.chat_completion", return_value="Mocked debate response"):
        result = runner.invoke(app, ["debate", "Lagrangian mechanics", "--rounds", "1"])
        assert result.exit_code == 0
        assert "Debate" in result.stdout or "Lagrangian" in result.stdout

def test_cli_study_command(runner):
    with patch("codex_mentis.cli.commands.study.check_prerequisites", return_value=["Algebra"]), \
         patch("codex_mentis.cli.commands.study.launch_repl") as mock_repl:
        result = runner.invoke(app, ["study", "Calculus"])
        assert result.exit_code == 0
        assert "Prerequisite concepts identified: Algebra" in result.stdout
        mock_repl.assert_called_once()

def test_cli_plot_command(runner):
    """Test the plot command."""
    result = runner.invoke(app, ["plot", "x**2"])
    assert result.exit_code == 0

def test_cli_verify_command(runner):
    """Test the verify command."""
    result = runner.invoke(app, ["verify", "1 + 1 = 2"])
    assert result.exit_code == 0
