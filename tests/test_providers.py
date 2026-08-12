import pytest
from codex_mentis.agents.providers import (
    create_provider,
    get_provider,
    FallbackProvider,
)
from codex_mentis.agents.providers.base import ProviderConfig
from codex_mentis.agents.providers.openai import OpenAIProvider
from tests.conftest import MockProvider


def test_provider_factory_creates_openai():
    """All providers go through OpenAI-compatible protocol."""
    config = ProviderConfig(api_key="key", model="gpt-4o")
    assert isinstance(create_provider(config), OpenAIProvider)


def test_provider_factory_gemini_via_openai():
    """Gemini models go through OpenAI-compatible (CLIProxy handles routing)."""
    config = ProviderConfig(api_key="key", model="google/gemini-3.6-flash-high")
    assert isinstance(create_provider(config), OpenAIProvider)


def test_provider_factory_claude_via_openai():
    """Claude models go through OpenAI-compatible (CLIProxy handles routing)."""
    config = ProviderConfig(api_key="key", model="claude-sonnet-4-20250514")
    assert isinstance(create_provider(config), OpenAIProvider)


def test_get_provider_returns_openai():
    """get_provider always returns OpenAI-compatible."""
    config = ProviderConfig(api_key="key", model="model")
    assert isinstance(get_provider("gpt", config), OpenAIProvider)
    assert isinstance(get_provider("claude", config), OpenAIProvider)
    assert isinstance(get_provider("gemini", config), OpenAIProvider)
    assert isinstance(get_provider("ollama", config), OpenAIProvider)


def test_fallback_provider():
    p1 = MockProvider()
    p2 = MockProvider()

    def fail_complete(*args, **kwargs):
        raise ValueError("API error")
    p1.complete = fail_complete

    p2.responses.append({"content": "Success from fallback", "tool_calls": []})

    fallback = FallbackProvider([p1, p2])
    res = fallback.complete([{"role": "user", "content": "hello"}])
    assert res["content"] == "Success from fallback"


def test_fallback_provider_all_fail():
    p1 = MockProvider()
    p2 = MockProvider()

    def fail(*args, **kwargs):
        raise ValueError("fail")
    p1.complete = fail
    p2.complete = fail

    fallback = FallbackProvider([p1, p2])
    with pytest.raises(RuntimeError, match="All providers failed"):
        fallback.complete([{"role": "user", "content": "hello"}])


def test_fallback_provider_embed():
    p1 = MockProvider()
    p2 = MockProvider()

    def fail_embed(*args, **kwargs):
        raise ValueError("Embedding error")
    p1.embed = fail_embed

    fallback = FallbackProvider([p1, p2])
    res = fallback.embed(["hello"])
    assert len(res) == 1
    assert len(res[0]) == 384
