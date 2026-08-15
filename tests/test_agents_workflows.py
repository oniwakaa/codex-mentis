import pytest

from pitagora.agents import BaseAgent
from pitagora.agents.workflows import WorkflowDefinition, WorkflowEngine, WorkflowStep


@pytest.mark.asyncio
async def test_workflow_engine(mock_provider):
    tutor = BaseAgent("tutor", "Tutor", mock_provider, "Tutor prompt")
    researcher = BaseAgent("researcher", "Researcher", mock_provider, "Researcher prompt")
    reviewer = BaseAgent("reviewer", "Reviewer", mock_provider, "Reviewer prompt")
    explainer = BaseAgent("explainer", "Explainer", mock_provider, "Explainer prompt")

    agents = {
        "tutor": tutor,
        "researcher": researcher,
        "reviewer": reviewer,
        "explainer": explainer,
    }

    engine = WorkflowEngine(agents=agents)

    mock_provider.responses.extend(
        [
            {"content": "Research result content", "tool_calls": []},
            {"content": "Extracted concepts content", "tool_calls": []},
            {"content": "Verified feedback content", "tool_calls": []},
            {"content": "Final synthesized master report", "tool_calls": []},
        ]
    )

    res = await engine.execute(
        inputs={"topic": "Quantum Gravity"}, workflow_name_or_def="deep_research"
    )

    assert res["workflow_name"] == "deep_research"
    assert engine.workflow.merge_strategy == "last"
    assert "search" in res["step_outputs"]
    assert res["step_outputs"]["search"] == "Research result content"
    assert res["step_outputs"]["extract"] == "Extracted concepts content"
    assert res["step_outputs"]["verify"] == "Verified feedback content"
    assert res["final_output"] == "Final synthesized master report"
