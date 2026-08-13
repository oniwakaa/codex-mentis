import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pitagora.cli.app as cli_app
from pitagora.cli.app import app
from pitagora.agents.base import AgentResponse

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
    
    with patch("pitagora.knowledge.acquisition.KnowledgeAcquisition.research_topic", return_value=mock_findings):
        result = runner.invoke(app, ["research", "quantum gravity", "--depth", "shallow"])
        assert result.exit_code == 0
        assert "Research Results: quantum gravity" in result.stdout
        assert "Finding 1" in result.stdout

def test_cli_explain_command(runner):
    with patch("pitagora.chat.chat_completion", return_value="Feynman explanation text"):
        result = runner.invoke(app, ["explain", "General Relativity", "--level", "beginner"])
        assert result.exit_code == 0
        assert "Feynman explanation text" in result.stdout

def test_cli_debate_command(runner):
    with patch("pitagora.chat.chat_completion", return_value="Mocked debate response"):
        result = runner.invoke(app, ["debate", "Lagrangian mechanics", "--rounds", "1"])
        assert result.exit_code == 0
        assert "Debate" in result.stdout or "Lagrangian" in result.stdout

def test_cli_study_command(runner):
    with patch("pitagora.cli.commands.study.check_prerequisites", return_value=["Algebra"]), \
         patch("pitagora.cli.commands.study.launch_repl") as mock_repl:
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


def test_select_chat_launcher_uses_simple_when_explicit():
    simple_launcher = MagicMock()

    with patch.object(cli_app, "_load_simple_launcher", return_value=simple_launcher), patch.object(
        cli_app, "_load_tui_launcher"
    ) as load_tui:
        selected = cli_app._select_chat_launcher(simple=True)

    assert selected is simple_launcher
    load_tui.assert_not_called()


def test_select_chat_launcher_uses_simple_when_not_interactive():
    simple_launcher = MagicMock()

    with patch.object(cli_app, "_is_interactive", return_value=False), patch.object(
        cli_app, "_load_simple_launcher", return_value=simple_launcher
    ), patch.object(cli_app, "_load_tui_launcher") as load_tui:
        selected = cli_app._select_chat_launcher(simple=False)

    assert selected is simple_launcher
    load_tui.assert_not_called()


def test_select_chat_launcher_uses_tui_in_interactive_terminal():
    tui_launcher = MagicMock()

    with patch.object(cli_app, "_is_interactive", return_value=True), patch.object(
        cli_app, "_load_tui_launcher", return_value=tui_launcher
    ):
        selected = cli_app._select_chat_launcher(simple=False)

    assert selected is tui_launcher


def test_select_chat_launcher_falls_back_when_textual_is_missing(capsys):
    simple_launcher = MagicMock()
    missing_textual = ModuleNotFoundError("No module named 'textual'", name="textual.widgets")

    with patch.object(cli_app, "_is_interactive", return_value=True), patch.object(
        cli_app, "_load_tui_launcher", side_effect=missing_textual
    ), patch.object(cli_app, "_load_simple_launcher", return_value=simple_launcher):
        selected = cli_app._select_chat_launcher(simple=False)

    assert selected is simple_launcher
    assert "pip install pitagora[tui]" in capsys.readouterr().out


def test_select_chat_launcher_reraises_unrelated_missing_module():
    missing_dependency = ModuleNotFoundError("No module named 'other'", name="other")

    with patch.object(cli_app, "_is_interactive", return_value=True), patch.object(
        cli_app, "_load_tui_launcher", side_effect=missing_dependency
    ):
        with pytest.raises(ModuleNotFoundError) as exc_info:
            cli_app._select_chat_launcher(simple=False)

    assert exc_info.value is missing_dependency
