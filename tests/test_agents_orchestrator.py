import pytest
import asyncio
from unittest.mock import MagicMock
from codex_mentis.agents import BaseAgent, AgentResponse, Orchestrator
from codex_mentis.agents.orchestrator import orchestrate, OrchestratorResponse

class DummyVisualizer(BaseAgent):
    def plot_expression(self, expr: str) -> str:
        return f"ASCII PLOT of {expr}"

@pytest.fixture
def orchestrator_agents(mock_provider):
    tutor = BaseAgent("Tutor", "Role", mock_provider, "Prompt")
    prover = BaseAgent("Prover", "Role", mock_provider, "Prompt")
    reviewer = BaseAgent("Reviewer", "Role", mock_provider, "Prompt")
    researcher = BaseAgent("Researcher", "Role", mock_provider, "Prompt")
    visualizer = DummyVisualizer("Visualizer", "Role", mock_provider, "Prompt")
    explainer = BaseAgent("Explainer", "Role", mock_provider, "Prompt")
    self_improver = BaseAgent("SelfImprover", "Role", mock_provider, "Prompt")
    
    return {
        "tutor": tutor,
        "prover": prover,
        "reviewer": reviewer,
        "researcher": researcher,
        "visualizer": visualizer,
        "explainer": explainer,
        "self_improver": self_improver
    }

@pytest.mark.asyncio
async def test_orchestrator_classify_intent(orchestrator_agents):
    orch = Orchestrator(agents=orchestrator_agents)
    
    # Check rule-based
    res = await orch.classify_intent("Let's run a debate between prover and reviewer")
    assert res["name"] == "prover_reviewer_debate"
    
    res = await orch.classify_intent("Plot x**2 + x")
    assert res["name"] == "visualizer"

@pytest.mark.asyncio
async def test_orchestrator_parallel_tutor_prover(orchestrator_agents, mock_provider):
    orch = Orchestrator(agents=orchestrator_agents)
    
    mock_provider.responses.extend([
        {"content": "Tutor explanation", "tool_calls": []},
        {"content": "Prover proof", "tool_calls": []}
    ])
    
    resp = await orch.aprocess("Derive pi", mode="parallel_tutor_prover")
    assert "Tutor explanation" in resp.content
    assert "Prover proof" in resp.content
    assert len(resp.agent_responses) == 2

@pytest.mark.asyncio
async def test_orchestrator_pipeline_workflow(orchestrator_agents, mock_provider):
    orch = Orchestrator(agents=orchestrator_agents)
    
    mock_provider.responses.extend([
        {"content": "Research material", "tool_calls": []},
        {"content": "Calculus proof $$y = x**2$$", "tool_calls": []},
        {"content": "Review check", "tool_calls": []}
    ])
    
    resp = await orch.aprocess("Study physics", mode="research_prove_review_visualize")
    assert "Research material" in resp.content
    assert "Calculus proof" in resp.content
    assert "ASCII PLOT of x**2" in resp.content

@pytest.mark.asyncio
async def test_orchestrator_debate_workflow(orchestrator_agents, mock_provider):
    orch = Orchestrator(agents=orchestrator_agents)
    
    mock_provider.responses.extend([
        {"content": "First proof", "tool_calls": []},
        {"content": "NO ERRORS DETECTED", "tool_calls": []}
    ])
    
    resp = await orch.aprocess("Prove relativity", mode="prover_reviewer_debate")
    assert "First proof" in resp.content
    assert "NO ERRORS DETECTED" in resp.content
    assert resp.metadata["rounds"] == 1

@pytest.mark.asyncio
async def test_orchestrator_derive_verify_plot(orchestrator_agents, mock_provider):
    orch = Orchestrator(agents=orchestrator_agents)
    
    mock_provider.responses.extend([
        {"content": "Derivation: $y = x**3$", "tool_calls": []},
        {"content": "Perfect verification", "tool_calls": []}
    ])
    
    resp = await orch.aprocess("Derive cube", mode="derive_verify_plot")
    assert "Perfect verification" in resp.content
    assert "ASCII PLOT of x**3" in resp.content

@pytest.mark.asyncio
async def test_orchestrate_standalone_dummy(monkeypatch):
    # Mock get_provider to return our MockProvider
    from codex_mentis.agents.providers import get_provider
    from codex_mentis.agents.providers.base import ProviderConfig
    from tests.conftest import MockProvider
    
    mock_prov = MockProvider()
    mock_prov.responses.append({"content": "Standalone Output", "tool_calls": []})
    
    monkeypatch.setattr("codex_mentis.agents.providers.get_provider", lambda name, config: mock_prov)
    
    # Also mock active agent classes inside orchestrate to use mock_prov
    # Wait, the orchestrate function calls TutorAgent(prov), ResearcherAgent(prov), etc.
    # Since they subclass BaseAgent, they will pass prov to BaseAgent.
    # Let's verify if that works. Yes, because they'll all receive the mock_prov from our patched get_provider!
    res = orchestrate(query="Solve algebra", mode="explore", topic="algebra")
    assert res == "Standalone Output"
