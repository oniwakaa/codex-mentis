import json
from unittest.mock import MagicMock

import pytest

from pitagora.agents import ExplainerAgent


@pytest.mark.asyncio
async def test_explainer_agent_difficulty_assessor(mock_provider):
    explainer = ExplainerAgent(mock_provider)

    # Mock structured output for DifficultyAssessment
    mock_provider.responses.append(
        {
            "content": '{"concept": "gravity", "estimated_difficulty": "easy", "prerequisites": ["mass"], "key_cognitive_obstacles": ["spacetime"]}',
            "tool_calls": [],
        }
    )

    res = await explainer.tool_difficulty_assessor("gravity")
    data = json.loads(res)
    assert data["concept"] == "gravity"
    assert data["estimated_difficulty"] == "easy"
    assert data["prerequisites"] == ["mass"]


@pytest.mark.asyncio
async def test_explainer_agent_analogy_generator(mock_provider):
    explainer = ExplainerAgent(mock_provider)

    # Mock structured output for Analogy
    mock_provider.responses.append(
        {
            "content": '{"concept": "electric current", "analogy_name": "water pipeline", "scenario": "water flowing in pipe", "mapping": {"voltage": "pressure"}, "limitations": ["water leaks"]}',
            "tool_calls": [],
        }
    )

    res = await explainer.tool_analogy_generator("electric current", "water")
    data = json.loads(res)
    assert data["concept"] == "electric current"
    assert data["analogy_name"] == "water pipeline"


@pytest.mark.asyncio
async def test_explainer_agent_concept_decomposer(mock_provider):
    explainer = ExplainerAgent(mock_provider)

    # Mock structured output for DecomposedConcept
    mock_provider.responses.append(
        {
            "content": '{"concept": "calculus", "sub_concepts": ["limits", "derivatives"], "milestones": ["understand limits"]}',
            "tool_calls": [],
        }
    )

    res = await explainer.tool_concept_decomposer("calculus")
    data = json.loads(res)
    assert data["concept"] == "calculus"
    assert "limits" in data["sub_concepts"]


@pytest.mark.asyncio
async def test_explainer_agent_explanations(mock_provider):
    explainer = ExplainerAgent(mock_provider)

    mock_provider.responses.extend(
        [
            {"content": "Level explanation", "tool_calls": []},
            {"content": "Feynman explanation", "tool_calls": []},
            {"content": "Intuition map", "tool_calls": []},
            {"content": "Side-by-side", "tool_calls": []},
        ]
    )

    resp_level = await explainer.explain_level("gravity", "Child")
    assert resp_level.content == "Level explanation"

    resp_fey = await explainer.feynman_explanation("gravity")
    assert resp_fey.content == "Feynman explanation"

    resp_map = await explainer.generate_intuition_map("gravity")
    assert resp_map.content == "Intuition map"

    resp_side = await explainer.side_by_side_explanation("gravity")
    assert resp_side.content == "Side-by-side"
