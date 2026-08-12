import pytest
import json
import os
from codex_mentis.agents import SelfImproverAgent

def test_self_improver_init_db(temp_db, mock_provider):
    improver = SelfImproverAgent(mock_provider, db_path=temp_db)
    assert os.path.exists(temp_db)
    # Check default strategies exist

def test_self_improver_select_strategy(temp_db, mock_provider):
    improver = SelfImproverAgent(mock_provider, db_path=temp_db)
    strategies = ["socratic", "feynman", "analogy"]
    chosen = improver.select_strategy(strategies)
    assert chosen in strategies

@pytest.mark.asyncio
async def test_self_improver_track_outcome(temp_db, mock_provider):
    improver = SelfImproverAgent(mock_provider, db_path=temp_db)
    
    # Track success
    res_success = await improver.tool_track_outcome(
        prompt_id="test_prompt_1",
        strategy_name="socratic",
        success=True,
        feedback="Understood easily"
    )
    data = json.loads(res_success)
    assert data["status"] == "success"
    assert data["new_alpha"] == 2.0  # default 1.0 + 1.0 success
    assert data["new_beta"] == 1.0
    
    # Track failure
    res_fail = await improver.tool_track_outcome(
        prompt_id="test_prompt_1",
        strategy_name="socratic",
        success=False,
        feedback="Confusing explanation"
    )
    data_fail = json.loads(res_fail)
    assert data_fail["new_alpha"] == 2.0
    assert data_fail["new_beta"] == 2.0  # default 1.0 + 1.0 failure

@pytest.mark.asyncio
async def test_self_improver_get_best_prompt(temp_db, mock_provider):
    improver = SelfImproverAgent(mock_provider, db_path=temp_db)
    
    # Record some outcomes for prompts
    await improver.tool_track_outcome("p1", "socratic", True)
    await improver.tool_track_outcome("p1", "socratic", True)
    await improver.tool_track_outcome("p2", "socratic", False)
    
    res = await improver.tool_get_best_prompt("socratic")
    data = json.loads(res)
    assert data["prompt_id"] == "p1"
    
    res_none = await improver.tool_get_best_prompt("nonexistent")
    data_none = json.loads(res_none)
    assert data_none["prompt_id"] == "nonexistent_default"

@pytest.mark.asyncio
async def test_self_improver_evolve_strategy(temp_db, mock_provider):
    improver = SelfImproverAgent(mock_provider, db_path=temp_db)
    
    # Record a failure
    await improver.tool_track_outcome("p1", "socratic", False, "Too formal, need child-friendly language")
    
    # Mock structured output for EvolvedPrompt
    mock_provider.responses.append({
        "content": '{"strategy_name": "socratic", "new_prompt_template": "Evolved prompt contents", "explanation_of_changes": "Simplified wording"}',
        "tool_calls": []
    })
    
    res = await improver.tool_evolve_strategy("socratic", "Current prompt template")
    data = json.loads(res)
    assert data["strategy_name"] == "socratic"
    assert data["new_prompt_template"] == "Evolved prompt contents"

@pytest.mark.asyncio
async def test_self_improver_generate_skill(temp_db, mock_provider):
    improver = SelfImproverAgent(mock_provider, db_path=temp_db)
    
    mock_provider.responses.append({
        "content": '{"skill_name": "socratic-algebra", "description": "Socratic algebra tutoring", "instructions": ["Ask questions", "Provide feedback"], "example_input": "x+2=4", "example_output": "What is x?"}',
        "tool_calls": []
    })
    
    res = await improver.tool_generate_skill("socratic-algebra", "Pattern summary")
    data = json.loads(res)
    assert data["skill_name"] == "socratic-algebra"
    assert data["description"] == "Socratic algebra tutoring"
