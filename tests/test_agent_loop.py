import asyncio
import time

import pytest

from pitagora.agents.guards import LoopGuard
from pitagora.agents.loop import AgentLoop, LoopConfig, LoopResult
from tests.conftest import MockProvider


@pytest.mark.asyncio
async def test_agent_loop_normal_completion(mock_provider):
    mock_provider.responses.append(
        {
            "content": "Final answer to question",
            "tool_calls": [],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            "cost_usd": 0.01,
        }
    )

    loop = AgentLoop(provider=mock_provider, config=LoopConfig(thinking_enabled=False))
    res = await loop.run("What is 2+2?", system_prompt="You are a tutor.")

    assert isinstance(res, LoopResult)
    assert res.response == "Final answer to question"
    assert res.stop_reason == "completed"
    assert res.iterations == 1
    assert res.total_tokens > 0
    assert res.total_cost_usd > 0.0


@pytest.mark.asyncio
async def test_agent_loop_max_iterations(mock_provider):
    # Return unique tool call responses to avoid doom loop detection
    for i in range(10):
        mock_provider.responses.append(
            {
                "content": f"Running tool call loop step {i}",
                "tool_calls": [{"name": "search", "arguments": {"query": f"test {i}"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
                "cost_usd": 0.001,
            }
        )

    config = LoopConfig(max_iterations=3, thinking_enabled=False)
    loop = AgentLoop(provider=mock_provider, config=config)
    res = await loop.run("Loop test")

    assert res.stop_reason == "max_iterations"
    assert res.iterations == 3


@pytest.mark.asyncio
async def test_agent_loop_timeout_stop(mock_provider):
    mock_provider.responses.append(
        {
            "content": "Loop step",
            "tool_calls": [{"name": "sleep_tool", "arguments": {}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            "cost_usd": 0.001,
        }
    )

    config = LoopConfig(wall_clock_timeout_s=1, thinking_enabled=False)
    guard = LoopGuard(wall_clock_timeout_s=1)
    loop = AgentLoop(provider=mock_provider, config=config, guard=guard)

    time.sleep(1.1)
    res = await loop.run("Timeout test")

    assert res.stop_reason == "timeout"


@pytest.mark.asyncio
async def test_agent_loop_cost_exceeded_stop(mock_provider):
    mock_provider.responses.append(
        {
            "content": "Expensive operation",
            "tool_calls": [{"name": "expensive", "arguments": {}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 100},
            "cost_usd": 5.00,  # Exceeds max_cost_usd of 2.0
        }
    )

    config = LoopConfig(max_cost_usd=2.0, thinking_enabled=False)
    loop = AgentLoop(provider=mock_provider, config=config)
    res = await loop.run("Cost test")

    assert res.stop_reason == "cost_exceeded"
    assert res.total_cost_usd >= 2.0


@pytest.mark.asyncio
async def test_agent_loop_doom_loop_detection(mock_provider):
    # Repeat exact same response twice with a tool call
    same_resp = {
        "content": "Identical doom loop response",
        "tool_calls": [{"name": "ping", "arguments": {}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
        "cost_usd": 0.001,
    }
    mock_provider.responses.extend([same_resp, same_resp])

    config = LoopConfig(thinking_enabled=False)
    loop = AgentLoop(provider=mock_provider, config=config)
    res = await loop.run("Doom loop test")

    assert res.stop_reason == "doom_loop"


@pytest.mark.asyncio
async def test_agent_loop_context_compaction_trigger(mock_provider):
    loop = AgentLoop(provider=mock_provider)
    # Populate large history
    loop._messages = [
        {"role": "system", "content": "Sys"},
        {"role": "user", "content": "Initial question"},
    ]
    for i in range(10):
        loop._messages.append({"role": "user", "content": f"Message block {i} " * 50})

    before_count = len(loop._messages)
    loop._compact_context()
    after_count = len(loop._messages)

    assert after_count < before_count
    assert any("[Previous context summary]" in m.get("content", "") for m in loop._messages)


@pytest.mark.asyncio
async def test_agent_loop_tool_execution(mock_provider):
    called = []

    def mock_handler(x: int) -> int:
        called.append(x)
        return x * 3

    tool_spec = {
        "name": "triple",
        "description": "Triple a number",
        "input_schema": {"properties": {"x": {"type": "integer"}}},
        "required_permission": "read",
        "handler": mock_handler,
    }

    mock_provider.responses.extend(
        [
            {
                "content": "Using tool",
                "tool_calls": [{"name": "triple", "arguments": {"x": 7}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "cost_usd": 0.001,
            },
            {
                "content": "Tool result is 21",
                "tool_calls": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "cost_usd": 0.001,
            },
        ]
    )

    loop = AgentLoop(
        provider=mock_provider, tools=[tool_spec], config=LoopConfig(thinking_enabled=False)
    )
    res = await loop.run("Calculate triple 7")

    assert res.stop_reason == "completed"
    assert res.response == "Tool result is 21"
    assert called == [7]
    assert len(res.tool_calls) == 1


@pytest.mark.asyncio
async def test_agent_loop_parallel_read_sequential_write(mock_provider):
    execution_order = []

    async def read_handler_1():
        execution_order.append("read1_start")
        await asyncio.sleep(0.02)
        execution_order.append("read1_end")
        return "read1"

    async def read_handler_2():
        execution_order.append("read2_start")
        await asyncio.sleep(0.02)
        execution_order.append("read2_end")
        return "read2"

    async def write_handler():
        execution_order.append("write_start")
        await asyncio.sleep(0.01)
        execution_order.append("write_end")
        return "write"

    t_read1 = {"name": "r1", "required_permission": "read", "handler": read_handler_1}
    t_read2 = {"name": "r2", "required_permission": "read", "handler": read_handler_2}
    t_write = {"name": "w1", "required_permission": "write", "handler": write_handler}

    loop = AgentLoop(provider=mock_provider, tools=[t_read1, t_read2, t_write])

    calls = [
        {"name": "r1", "arguments": {}},
        {"name": "r2", "arguments": {}},
        {"name": "w1", "arguments": {}},
    ]
    results = await loop._execute_tools_parallel(calls)

    assert len(results) == 3
    # Reads start before writes
    assert execution_order.index("read1_start") < execution_order.index("write_start")
    assert execution_order.index("read2_start") < execution_order.index("write_start")


@pytest.mark.asyncio
async def test_agent_loop_with_thinking_phase(mock_provider):
    mock_provider.responses.extend(
        [
            # Thinking phase response
            {
                "content": "I need to analyze this query.",
                "tool_calls": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            },
            # Action phase response
            {
                "content": "Here is the answer.",
                "tool_calls": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            },
        ]
    )

    loop = AgentLoop(provider=mock_provider, config=LoopConfig(thinking_enabled=True))
    res = await loop.run("Question with thinking")

    assert res.response == "Here is the answer."
    assert res.stop_reason == "completed"


@pytest.mark.asyncio
async def test_agent_loop_result_metadata(mock_provider):
    mock_provider.responses.append(
        {
            "content": "Response with metadata",
            "tool_calls": [],
            "usage": {"prompt_tokens": 15, "completion_tokens": 25},
            "cost_usd": 0.005,
        }
    )

    loop = AgentLoop(provider=mock_provider, config=LoopConfig(thinking_enabled=False))
    res = await loop.run("Test metadata")

    assert res.session_id.startswith("session_")
    assert res.total_tokens == 40
    assert res.total_cost_usd == pytest.approx(0.005)


@pytest.mark.asyncio
async def test_agent_loop_with_tool_registry(mock_provider):
    from pitagora.agents.tools.registry import ToolRegistry, ToolSpec

    registry = ToolRegistry()

    async def double(n: int) -> dict:
        return {"result": n * 2}

    registry.register(
        ToolSpec(
            name="double",
            description="Double a number",
            input_schema={"type": "object", "properties": {"n": {"type": "integer"}}},
            required_permission="read",
            category="math",
            handler=double,
        )
    )

    mock_provider.responses.extend(
        [
            {
                "content": "Using double tool",
                "tool_calls": [{"name": "double", "arguments": {"n": 21}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            },
            {
                "content": "The answer is 42.",
                "tool_calls": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            },
        ]
    )

    loop = AgentLoop(
        provider=mock_provider, tools=registry, config=LoopConfig(thinking_enabled=False)
    )
    res = await loop.run("What is 21 * 2?")

    assert res.response == "The answer is 42."
    assert res.stop_reason == "completed"
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0]["call"]["name"] == "double"
