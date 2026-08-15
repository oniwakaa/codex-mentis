import pytest

from pitagora.agents.context import ContextManager
from pitagora.agents.loop import AgentLoop, LoopConfig
from tests.conftest import MockProvider


def test_context_under_threshold_no_compaction():
    cm = ContextManager(max_tokens=1000)
    messages = [
        {"role": "system", "content": "Short prompt"},
        {"role": "user", "content": "Short question"},
    ]
    assert cm.needs_compaction(messages) is False
    assert cm.compact(messages) == messages


def test_context_over_threshold_compaction_triggered():
    cm = ContextManager(max_tokens=100)  # Threshold = 80 tokens (~320 chars)
    messages = [
        {"role": "system", "content": "Sys prompt"},
        {"role": "user", "content": "First question"},
    ]
    for i in range(15):
        messages.append({"role": "assistant", "content": f"Block content {i} " * 20})

    assert cm.needs_compaction(messages) is True
    compacted = cm.compact(messages, keep_recent=4)

    # 2 initial + 1 summary + 4 recent = 7 messages
    assert len(compacted) == 7
    assert compacted[0] == messages[0]
    assert compacted[1] == messages[1]
    assert "[Compacted context" in compacted[2]["content"]
    assert compacted[-4:] == messages[-4:]


def test_context_summary_correctness():
    cm = ContextManager()
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1 response"},
        {"role": "tool", "content": "t1 result"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2 response"},
    ]
    compacted = cm.compact(messages, keep_recent=2)
    summary_text = compacted[2]["content"]

    assert "[Compacted context — 2 messages summarized]" in summary_text
    assert "[assistant] a1 response" in summary_text
    assert "[tool] t1 result" in summary_text


@pytest.mark.asyncio
async def test_integration_loop_with_compaction(mock_provider):
    mock_provider.responses.append(
        {
            "content": "Compacted continuation answer",
            "tool_calls": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
        }
    )

    cm = ContextManager(max_tokens=50)
    loop = AgentLoop(provider=mock_provider, config=LoopConfig(thinking_enabled=False))

    # Populate large conversation in loop
    loop._messages = [
        {"role": "system", "content": "Sys prompt"},
        {"role": "user", "content": "Initial user question"},
    ]
    for i in range(10):
        loop._messages.append({"role": "user", "content": f"Long turn {i} " * 20})

    res = await loop.run("Continuation query")
    assert res.stop_reason == "completed"
    assert res.response == "Compacted continuation answer"
