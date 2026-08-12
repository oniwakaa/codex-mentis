import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
from codex_mentis.cli.app import app
from codex_mentis.agents import AgentResponse

@pytest.fixture
def runner():
    return CliRunner()

def test_cli_research_command(runner):
    # Mock research_topic return value
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
        assert "Concept A" in result.stdout

def test_cli_explain_command(runner):
    mock_resp = AgentResponse(content="Feynman explanation text", tool_calls=[])
    
    with patch("codex_mentis.agents.explainer.ExplainerAgent.explain_level", return_value=mock_resp) as mock_explain:
        result = runner.invoke(app, ["explain", "General Relativity", "--level", "beginner"])
        assert result.exit_code == 0
        assert "Feynman explanation text" in result.stdout or "Configure a provider" in result.stdout

def test_cli_debate_command(runner):
    result = runner.invoke(app, ["debate", "Lagrangian mechanics", "--rounds", "2"])
    assert result.exit_code == 0
    assert "Debate: Lagrangian mechanics" in result.stdout

def test_cli_study_command(runner):
    # Mock check_prerequisites and launch_repl
    with patch("codex_mentis.cli.commands.study.check_prerequisites", return_value=["Algebra"]), \
         patch("codex_mentis.cli.commands.study.launch_repl") as mock_repl:
        result = runner.invoke(app, ["study", "Calculus"])
        assert result.exit_code == 0
        assert "Prerequisite concepts identified: Algebra" in result.stdout
        mock_repl.assert_called_once()
