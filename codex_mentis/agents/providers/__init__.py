import logging
from typing import Dict, Any, List, Optional, AsyncIterator, Iterator
from codex_mentis.agents.providers.base import BaseProvider, ProviderConfig
from codex_mentis.agents.providers.openai import OpenAIProvider
from codex_mentis.agents.providers.anthropic import AnthropicProvider
from codex_mentis.agents.providers.gemini import GeminiProvider
from codex_mentis.agents.providers.local import LocalProvider

logger = logging.getLogger(__name__)

class FallbackProvider(BaseProvider):
    def __init__(self, providers: List[BaseProvider]):
        if not providers:
            raise ValueError("FallbackProvider requires at least one provider.")
        super().__init__(providers[0].config)
        self.providers = providers

    def complete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        last_exception = None
        for provider in self.providers:
            try:
                return provider.complete(messages, tools, temperature, response_format)
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed: {e}. Trying fallback...")
                last_exception = e
        raise RuntimeError(f"All providers in fallback chain failed. Last error: {last_exception}")

    async def acomplete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        last_exception = None
        for provider in self.providers:
            try:
                return await provider.acomplete(messages, tools, temperature, response_format)
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed: {e}. Trying fallback...")
                last_exception = e
        raise RuntimeError(f"All providers in fallback chain failed. Last error: {last_exception}")

    def stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        # Streams usually don't support mid-stream fallback easily, but we fall back on initial connection
        last_exception = None
        for provider in self.providers:
            try:
                # Retrieve generator to test connection/handshake
                gen = provider.stream(messages)
                return gen
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed to start stream: {e}. Trying fallback...")
                last_exception = e
        raise RuntimeError(f"All providers in fallback stream chain failed. Last error: {last_exception}")

    async def astream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        last_exception = None
        for provider in self.providers:
            try:
                # We return the async iterator from the first succeeding provider
                gen = provider.astream(messages)
                return gen
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed to start stream: {e}. Trying fallback...")
                last_exception = e
        raise RuntimeError(f"All providers in fallback stream chain failed. Last error: {last_exception}")

    def embed(self, texts: List[str]) -> List[List[float]]:
        last_exception = None
        for provider in self.providers:
            try:
                return provider.embed(texts)
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed to embed: {e}. Trying fallback...")
                last_exception = e
        raise RuntimeError(f"All providers in fallback embed chain failed. Last error: {last_exception}")

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        last_exception = None
        for provider in self.providers:
            try:
                return await provider.aembed(texts)
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed to embed: {e}. Trying fallback...")
                last_exception = e
        raise RuntimeError(f"All providers in fallback embed chain failed. Last error: {last_exception}")

def create_provider(config: ProviderConfig) -> BaseProvider:
    """
    Factory to create a provider based on ProviderConfig.
    Resolves aliases and handles config analysis.
    If a fallback_chain list is provided in extra_params, returns a FallbackProvider.
    """
    # 1. Check for fallback chain in config extra_params
    fallback_chain = config.extra_params.get("fallback_chain")
    if fallback_chain and isinstance(fallback_chain, list):
        providers = []
        for p_name in fallback_chain:
            # Construct a sub-config with the specific provider model/base_url if specified in extra_params
            p_config_dict = config.extra_params.get(f"config_{p_name}", {})
            sub_config = ProviderConfig(
                api_key=p_config_dict.get("api_key", config.api_key),
                model=p_config_dict.get("model", config.model),
                base_url=p_config_dict.get("base_url", config.base_url),
                max_tokens=p_config_dict.get("max_tokens", config.max_tokens),
                timeout=p_config_dict.get("timeout", config.timeout),
                max_retries=p_config_dict.get("max_retries", config.max_retries),
                initial_backoff=p_config_dict.get("initial_backoff", config.initial_backoff),
                backoff_factor=p_config_dict.get("backoff_factor", config.backoff_factor),
                extra_params=p_config_dict.get("extra_params", config.extra_params.copy())
            )
            # Remove fallback_chain from sub-configs to avoid infinite loop
            if "fallback_chain" in sub_config.extra_params:
                del sub_config.extra_params["fallback_chain"]
            providers.append(get_provider(p_name, sub_config))
        return FallbackProvider(providers)

    # 2. Extract provider type from model name or default config
    model_name = (config.model or "").lower()
    
    # Check model prefixes/substrings for auto-routing
    if "gpt" in model_name or "o1-" in model_name or "o3-" in model_name:
        return OpenAIProvider(config)
    elif "claude" in model_name:
        return AnthropicProvider(config)
    elif "gemini" in model_name:
        return GeminiProvider(config)
    elif "llama" in model_name or "ollama" in model_name or "local" in model_name:
        return LocalProvider(config)

    # Fallback to base_url patterns
    base_url = (config.base_url or "").lower()
    if "openai" in base_url:
        return OpenAIProvider(config)
    elif "anthropic" in base_url:
        return AnthropicProvider(config)
    elif "googleapis" in base_url:
        return GeminiProvider(config)
    elif "localhost" in base_url or "127.0.0.1" in base_url or "11434" in base_url:
        return LocalProvider(config)

    # Absolute fallback: OpenAI compatible endpoint
    return OpenAIProvider(config)

def get_provider(provider_name: str, config: ProviderConfig) -> BaseProvider:
    """
    Backward-compatible entrypoint mapping names/aliases to specific provider instances.
    """
    name = provider_name.lower().strip()
    
    # Resolve aliases
    if name in ("openai", "gpt", "gpt-4o", "gpt-3.5", "chatgpt"):
        return OpenAIProvider(config)
    elif name in ("anthropic", "claude", "claude-3", "sonnet", "opus"):
        return AnthropicProvider(config)
    elif name in ("gemini", "google", "generative-language", "flash", "pro"):
        return GeminiProvider(config)
    elif name in ("local", "llama", "ollama", "vllm", "llama-cpp"):
        return LocalProvider(config)
    else:
        # Fall back to using create_provider's dynamic inspection
        return create_provider(config)
