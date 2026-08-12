import pytest
import asyncio
from pydantic import BaseModel
from codex_mentis.agents import BaseAgent, AgentResponse
from codex_mentis.agents.base import validate_json_schema

def test_agent_response_creation():
    resp = AgentResponse(content="Hello", confidence=0.8, metadata={"test": "yes"})
    assert resp.content == "Hello"
    assert resp.confidence == 0.8
    assert resp.metadata == {"test": "yes"}
    assert resp.tool_calls == []

def test_validate_json_schema():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "integer"}
        },
        "required": ["name"]
    }
    
    # Valid data
    assert validate_json_schema(schema, {"name": "test", "value": 123}) == []
    
    # Missing required
    errors = validate_json_schema(schema, {"value": 123})
    assert any("Missing required property" in err for err in errors)
    
    # Type mismatch
    errors = validate_json_schema(schema, {"name": 123})
    assert any("Expected string" in err for err in errors)

def test_base_agent_tool_registration(mock_provider):
    agent = BaseAgent(
        name="TestBase",
        role="Tester",
        provider=mock_provider,
        system_prompt="You are a tester."
    )
    
    def my_handler(x: int) -> int:
        return x * 2

    schema = {
        "name": "double",
        "description": "Double a number",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"}
            },
            "required": ["x"]
        }
    }
    
    agent.register_tool("double", schema, my_handler)
    assert "double" in agent.tool_handlers
    assert "double" in agent.tool_schemas
    
    res = agent.with_tool("double", {"x": 5})
    assert res == 10
    
    # Invalid args validation
    res_err = agent.with_tool("double", {"x": "not-an-int"})
    assert "Validation failed" in res_err

@pytest.mark.asyncio
async def test_base_agent_think(mock_provider):
    agent = BaseAgent(
        name="TestBase",
        role="Tester",
        provider=mock_provider,
        system_prompt="System prompt"
    )
    
    # Synchronous think
    mock_provider.responses.append({
        "content": "Sync response",
        "tool_calls": [],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5}
    })
    
    resp = agent.think("Hello Sync")
    assert resp.content == "Sync response"
    assert agent.token_usage["total_tokens"] > 0
    
    # Asynchronous think
    mock_provider.responses.append({
        "content": "Async response",
        "tool_calls": [],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5}
    })
    resp_async = await agent.athink("Hello Async")
    assert resp_async.content == "Async response"

def test_history_management(mock_provider):
    agent = BaseAgent(
        name="TestBase",
        role="Tester",
        provider=mock_provider,
        system_prompt="System prompt",
        max_history_len=3
    )
    
    agent.add_message("user", "1")
    agent.add_message("assistant", "2")
    agent.add_message("user", "3")
    agent.add_message("assistant", "4")
    
    history = agent.get_history()
    # Expecting 3 messages, with the first kept if it is system (it wasn't in history yet, or wait, it handles system retention)
    # Let's check how many messages are kept: max_history_len is 3.
    assert len(history) == 3
    assert history[-1]["content"] == "4"
    assert history[0]["content"] == "2"

@pytest.mark.asyncio
async def test_athink_structured(mock_provider):
    class OutputModel(BaseModel):
        val: int
        msg: str

    agent = BaseAgent(
        name="TestBase",
        role="Tester",
        provider=mock_provider,
        system_prompt="System prompt"
    )
    
    mock_provider.responses.append({
        "content": '{"val": 42, "msg": "success"}',
        "tool_calls": [],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5}
    })
    
    res = await agent.athink_structured("Get answer", OutputModel)
    assert res.val == 42
    assert res.msg == "success"

def test_confidence_calculation(mock_provider):
    agent = BaseAgent(
        name="TestBase",
        role="Tester",
        provider=mock_provider,
        system_prompt="System prompt"
    )
    
    # Parsing confidence from tags
    c = agent._calculate_confidence("<confidence>0.85</confidence>", {})
    assert c == 0.85
    
    # Guessing from words
    c_unsure = agent._calculate_confidence("I am unsure about this.", {})
    assert c_unsure == 0.7
    
    # Default
    c_def = agent._calculate_confidence("Standard answer.", {})
    assert c_def == 1.0
