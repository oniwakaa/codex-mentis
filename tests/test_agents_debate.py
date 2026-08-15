import pytest

from pitagora.agents import BaseAgent
from pitagora.agents.debate import DebateAgent


@pytest.mark.asyncio
async def test_debate_agent(mock_provider):
    prover = BaseAgent("prover", "Prover", mock_provider, "Prover prompt")
    reviewer = BaseAgent("reviewer", "Reviewer", mock_provider, "Reviewer prompt")
    debate_mgr = DebateAgent(mock_provider)

    mock_provider.responses.extend(
        [
            {"content": "Prover Opening statement", "tool_calls": []},
            {"content": "Reviewer Opening statement", "tool_calls": []},
            {"content": "Reviewer critique", "tool_calls": []},
            {"content": "Prover response to critique", "tool_calls": []},
            {"content": "Prover critique of Reviewer", "tool_calls": []},
            {"content": "Reviewer response", "tool_calls": []},
            {"content": "Prover rebuttal", "tool_calls": []},
            {"content": "Reviewer rebuttal", "tool_calls": []},
            {"content": "Prover closing", "tool_calls": []},
            {"content": "Reviewer closing", "tool_calls": []},
            {
                "content": '{"verdict": "FOR", "confidence": 0.85, "strongest_arguments_pro": ["axiom A holds"], "strongest_arguments_con": ["edge case B exists"], "synthesis_summary": "Reconciliation summary."}',
                "tool_calls": [],
            },
        ]
    )

    res = await debate_mgr.run_debate(statement="P = NP", prover=prover, reviewer=reviewer)

    assert res["verdict"] == "FOR"
    assert res["confidence"] == 0.85
    assert "Prover Opening statement" in res["transcript"][0]["content"]
