import pytest

from pitagora.agents import BaseAgent
from pitagora.agents.chain_of_thought import ReasoningChain


@pytest.mark.asyncio
async def test_reasoning_chain(mock_provider):
    prover = BaseAgent("prover", "Prover", mock_provider, "Prover prompt")
    reviewer = BaseAgent("reviewer", "Reviewer", mock_provider, "Reviewer prompt")

    chain = ReasoningChain(
        prover=prover, reviewer=reviewer, max_depth=3, max_branches=2, max_revisions=1
    )

    mock_provider.responses.extend(
        [
            {"content": "Thought 1", "tool_calls": []},
            {"content": "FAILED: error in definition", "tool_calls": []},
            {"content": "Thought 1 Revised", "tool_calls": []},
            {"content": "FAILED: still incorrect", "tool_calls": []},
            {"content": "Thought 2 alternative", "tool_calls": []},
            {"content": "VERIFIED: correct approach", "tool_calls": []},
            {"content": "Thought 3 QED", "tool_calls": []},
            {"content": "VERIFIED: correct", "tool_calls": []},
        ]
    )

    res = await chain.solve("Prove theorem X")

    assert res["success"] is True
    assert "Thought 2 alternative" in res["solution"]
    assert "Thought 3 QED" in res["solution"]

    tree_vis = res["tree_visualization"]
    assert "Step 1: Thought 1 Revised [FAILED]" in tree_vis
    assert "Step 2: Thought 2 alternative [VERIFIED]" in tree_vis
    assert "Step 2.1: Thought 3 QED [VERIFIED]" in tree_vis
