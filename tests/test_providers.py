import pytest
from codex_mentis.agents.providers import (
    ProviderConfig,
    create_provider,
    get_provider,
    FallbackProvider
)
from codex_mentis.agents.providers.openai import OpenAIProvider
from codex_mentis.agents.providers.anthropic import AnthropicProvider
from codex_mentis.agents.providers.gemini import GeminiProvider
from codex_mentis.agents.providers.local import LocalProvider
from tests.conftest import MockProvider

def test_provider_factory_routing():
    config_openai = ProviderConfig(api_key="key", model="gpt-4o")
    assert isinstance(create_provider(config_openai), OpenAIProvider)
    
    config_anthropic = ProviderConfig(api_key="key", model="claude-3-5-sonnet")
    assert isinstance(create_provider(config_anthropic), AnthropicProvider)
    
    config_gemini = ProviderConfig(api_key="key", model="gemini-1.5-flash")
    assert isinstance(create_provider(config_gemini), GeminiProvider)
    
    config_local = ProviderConfig(api_key="key", model="llama-3-8b")
    assert isinstance(create_provider(config_local), LocalProvider)

def test_get_provider_aliases():
    config = ProviderConfig(api_key="key", model="model")
    assert isinstance(get_provider("gpt", config), OpenAIProvider)
    assert isinstance(get_provider("claude", config), AnthropicProvider)
    assert isinstance(get_provider("google", config), GeminiProvider)
    assert isinstance(get_provider("ollama", config), LocalProvider)

def test_fallback_provider():
    p1 = MockProvider()
    p2 = MockProvider()
    
    # Mock p1 to fail
    def fail_complete(*args, **kwargs):
        raise ValueError("API error")
    p1.complete = fail_complete
    
    # Mock p2 to succeed
    p2.responses.append({"content": "Success from fallback", "tool_calls": []})
    
    fallback = FallbackProvider([p1, p2])
    res = fallback.complete([{"role": "user", "content": "hello"}])
    assert res["content"] == "Success from fallback"

@pytest.mark.asyncio
async def test_fallback_provider_async():
    p1 = MockProvider()
    p2 = MockProvider()
    
    async def fail_acomplete(*args, **kwargs):
        raise ValueError("API error")
    p1.acomplete = fail_acomplete
    
    p2.responses.append({"content": "Success async", "tool_calls": []})
    
    fallback = FallbackProvider([p1, p2])
    res = await fallback.acomplete([{"role": "user", "content": "hello"}])
    assert res["content"] == "Success async"

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
