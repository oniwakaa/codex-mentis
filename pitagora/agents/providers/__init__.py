"""Provider system — OpenAI-compatible provider with fallback chains.

All providers (OpenAI, Anthropic via proxy, Gemini via CLIProxy, Ollama, local)
are handled through the OpenAI-compatible protocol. CLIProxy routes to the
correct backend automatically.
"""
import logging
from typing import Dict, Any, List, Optional, Iterator
from pitagora.agents.providers.base import BaseProvider, ProviderConfig
from pitagora.agents.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


class FallbackProvider(BaseProvider):
    """Try multiple providers in sequence, falling back on failure."""

    def __init__(self, providers: List[BaseProvider]):
        if not providers:
            raise ValueError("FallbackProvider requires at least one provider.")
        super().__init__(providers[0].config)
        self.providers = providers

    def complete(self, messages, tools=None, temperature=0.7, response_format=None):
        last_err = None
        for p in self.providers:
            try:
                return p.complete(messages, tools, temperature, response_format)
            except Exception as e:
                logger.warning(f"{p.__class__.__name__} failed: {e}")
                last_err = e
        raise RuntimeError(f"All providers failed. Last: {last_err}")

    def stream(self, messages):
        for p in self.providers:
            try:
                return p.stream(messages)
            except Exception as e:
                logger.warning(f"{p.__class__.__name__} stream failed: {e}")
        raise RuntimeError("All providers failed to stream")

    def embed(self, texts):
        for p in self.providers:
            try:
                return p.embed(texts)
            except Exception as e:
                logger.warning(f"{p.__class__.__name__} embed failed: {e}")
        raise RuntimeError("All providers failed to embed")


def create_provider(config: ProviderConfig) -> BaseProvider:
    """Create a provider. Everything goes through OpenAI-compatible protocol.

    CLIProxy, Ollama, vLLM, and direct OpenAI all speak the same API.
    For Anthropic/Gemini, use CLIProxy to translate.
    """
    # Check for fallback chain
    fallback_chain = config.extra_params.get("fallback_chain")
    if fallback_chain and isinstance(fallback_chain, list):
        providers = []
        for p_name in fallback_chain:
            p_config_dict = config.extra_params.get(f"config_{p_name}", {})
            sub_config = ProviderConfig(
                api_key=p_config_dict.get("api_key", config.api_key),
                model=p_config_dict.get("model", config.model),
                base_url=p_config_dict.get("base_url", config.base_url),
                max_tokens=p_config_dict.get("max_tokens", config.max_tokens),
            )
            providers.append(OpenAIProvider(sub_config))
        return FallbackProvider(providers)

    return OpenAIProvider(config)


def get_provider(provider_name: str, config: ProviderConfig) -> BaseProvider:
    """Create provider by name. All route through OpenAI-compatible."""
    return OpenAIProvider(config)
