import pytest
from unittest.mock import patch
from pitagora.agents.orchestrator import Orchestrator, OrchestratorResponse
from pitagora.agents.base import AgentResponse


class MockAgent:
    """Lightweight mock agent for orchestrator tests — all methods async."""
    def __init__(self, name="Mock", response="Default response"):
        self.name = name
        self.role = "mock"
        self._response = response
        self.tools = []
    
    def think(self, prompt, context=None):
        return AgentResponse(content=self._response, tool_calls=[], confidence=0.9, metadata={})
    
    async def athink(self, prompt, context=None):
        return AgentResponse(content=self._response, tool_calls=[], confidence=0.9, metadata={})
    
    async def explain_concept(self, topic, level="beginner"):
        return AgentResponse(content=f"Explaining {topic}", tool_calls=[], confidence=0.9, metadata={})
    
    async def feynman_explanation(self, topic):
        return AgentResponse(content=f"Feynman: {topic}", tool_calls=[], confidence=0.9, metadata={})
    
    async def explain_level(self, topic, level="intermediate"):
        return AgentResponse(content=f"Explaining {topic} at {level}", tool_calls=[], confidence=0.9, metadata={})
    
    async def tool_analogy_generator(self, topic, domain="everyday life"):
        return f"Analogy for {topic}"
    
    async def research(self, topic, depth="medium"):
        return AgentResponse(content=f"Research on {topic}", tool_calls=[], confidence=0.8, metadata={})
    
    async def derive(self, request):
        return AgentResponse(content=f"Derivation of {request}", tool_calls=[], confidence=0.95, metadata={})
    
    async def review(self, claim):
        return AgentResponse(content=f"Review of {claim}", tool_calls=[], confidence=0.85, metadata={})
    
    def plot_expression(self, expr, **kwargs):
        return f"ASCII PLOT of {expr}"


def test_orchestrator_routing():
    agents = {
        "tutor": MockAgent("Tutor", "Socratic answer"),
        "researcher": MockAgent("Researcher", "Research findings"),
        "prover": MockAgent("Prover", "Derivation proof"),
        "reviewer": MockAgent("Reviewer", "Review verdict"),
        "visualizer": MockAgent("Visualizer", "Plot output"),
        "explainer": MockAgent("Explainer", "Simple explanation"),
    }
    orch = Orchestrator(agents=agents)
    
    resp = orch.process("Explain calculus", mode="study")
    assert isinstance(resp, OrchestratorResponse)
    assert len(resp.content) > 0
    
    resp = orch.process("Search for papers", mode="explore")
    assert isinstance(resp, OrchestratorResponse)


def test_orchestrator_derive_verify_plot():
    agents = {
        "prover": MockAgent("Prover", "Step 1: ... Step 2: ..."),
        "reviewer": MockAgent("Reviewer", "CONFIRMED. Confidence: 0.95"),
        "visualizer": MockAgent("Visualizer", "ASCII PLOT of x**3"),
    }
    orch = Orchestrator(agents=agents)
    
    resp = orch.process("derive Euler-Lagrange", mode="multi")
    assert isinstance(resp, OrchestratorResponse)
    assert len(resp.content) > 0


def test_orchestrate_standalone():
    """Test the standalone orchestrate function with a mocked provider."""
    from pitagora.agents.orchestrator import orchestrate
    from tests.conftest import MockProvider
    
    mock_prov = MockProvider()
    mock_prov.responses.append({
        "content": "Standalone Output",
        "tool_calls": [],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5}
    })
    
    with patch("pitagora.agents.providers.get_provider", return_value=mock_prov):
        res = orchestrate(query="Solve algebra", mode="explore", topic="algebra")
    
    assert isinstance(res, str)
    assert len(res) > 0
