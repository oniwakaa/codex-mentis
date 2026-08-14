"""OpenAI-compatible provider factory and fallback chain."""

import logging
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from typing import Any

from pitagora.agents.providers.base import BaseProvider, ProviderConfig
from pitagora.agents.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


class FallbackProvider(BaseProvider):
    """Try providers in order and account for the successful provider."""

    def __init__(self, providers: Sequence[BaseProvider]):
        if not providers:
            raise ValueError("FallbackProvider requires at least one provider.")
        super().__init__(providers[0].config)
        self.providers = list(providers)

    def _record_result(self, result: dict[str, Any], provider: BaseProvider) -> None:
        usage = result.get("usage")
        if not isinstance(usage, Mapping):
            return
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        if all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in (prompt_tokens, completion_tokens, total_tokens)
        ):
            self._record_usage(
                {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
                config=provider.config,
            )

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                result = provider.complete(messages, tools, temperature, response_format)
            except Exception as error:  # noqa: BLE001 - fallback must handle provider failures
                logger.warning("%s failed: %s", provider.__class__.__name__, error)
                last_error = error
                continue
            self._record_result(result, provider)
            return result
        raise RuntimeError(f"All providers failed. Last: {last_error}") from last_error

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        last_error: Exception | None = None
        for provider in self.providers:
            yielded = False
            try:
                for chunk in provider.stream(messages):
                    yielded = True
                    yield chunk
                return
            except Exception as error:  # noqa: BLE001 - fallback must handle provider failures
                if yielded:
                    raise
                logger.warning("%s stream failed: %s", provider.__class__.__name__, error)
                last_error = error
        raise RuntimeError(f"All providers failed to stream. Last: {last_error}") from last_error

    def embed(self, texts: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                return provider.embed(texts)
            except Exception as error:  # noqa: BLE001 - fallback must handle provider failures
                logger.warning("%s embed failed: %s", provider.__class__.__name__, error)
                last_error = error
        raise RuntimeError(f"All providers failed to embed. Last: {last_error}") from last_error

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                result = await provider.acomplete(
                    messages,
                    tools,
                    temperature,
                    response_format,
                )
            except Exception as error:  # noqa: BLE001 - fallback must handle provider failures
                logger.warning("%s acomplete failed: %s", provider.__class__.__name__, error)
                last_error = error
                continue
            self._record_result(result, provider)
            return result
        raise RuntimeError(f"All providers failed. Last: {last_error}") from last_error

    async def astream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        last_error: Exception | None = None
        for provider in self.providers:
            yielded = False
            try:
                async for chunk in provider.astream(messages):
                    yielded = True
                    yield chunk
                return
            except Exception as error:  # noqa: BLE001 - fallback must handle provider failures
                if yielded:
                    raise
                logger.warning("%s astream failed: %s", provider.__class__.__name__, error)
                last_error = error
        raise RuntimeError(f"All providers failed to astream. Last: {last_error}") from last_error

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                return await provider.aembed(texts)
            except Exception as error:  # noqa: BLE001 - fallback must handle provider failures
                logger.warning("%s aembed failed: %s", provider.__class__.__name__, error)
                last_error = error
        raise RuntimeError(f"All providers failed to aembed. Last: {last_error}") from last_error


def create_provider(config: ProviderConfig) -> BaseProvider:
    """Create an OpenAI-compatible provider, optionally with fallbacks."""
    fallback_chain = config.extra_params.get("fallback_chain")
    if isinstance(fallback_chain, list) and fallback_chain:
        providers: list[BaseProvider] = []
        for provider_name in fallback_chain:
            provider_config = config.extra_params.get(f"config_{provider_name}", {})
            if not isinstance(provider_config, dict):
                raise ValueError(f"config_{provider_name} must be an object")
            providers.append(
                OpenAIProvider(
                    ProviderConfig(
                        api_key=provider_config.get("api_key", config.api_key),
                        model=provider_config.get("model", config.model),
                        base_url=provider_config.get("base_url", config.base_url),
                        max_tokens=provider_config.get("max_tokens", config.max_tokens),
                        timeout=provider_config.get("timeout", config.timeout),
                        connect_timeout=provider_config.get(
                            "connect_timeout",
                            config.connect_timeout,
                        ),
                        read_timeout=provider_config.get("read_timeout", config.read_timeout),
                        write_timeout=provider_config.get("write_timeout", config.write_timeout),
                        pool_timeout=provider_config.get("pool_timeout", config.pool_timeout),
                        max_retries=provider_config.get("max_retries", config.max_retries),
                        initial_backoff=provider_config.get(
                            "initial_backoff",
                            config.initial_backoff,
                        ),
                        backoff_factor=provider_config.get(
                            "backoff_factor",
                            config.backoff_factor,
                        ),
                        prompt_token_cost=provider_config.get(
                            "prompt_token_cost",
                            config.prompt_token_cost,
                        ),
                        completion_token_cost=provider_config.get(
                            "completion_token_cost",
                            config.completion_token_cost,
                        ),
                        extra_params=provider_config.get("extra_params", {}),
                    )
                )
            )
        return FallbackProvider(providers)
    return OpenAIProvider(config)


def get_provider(provider_name: str, config: ProviderConfig) -> BaseProvider:
    """Create a provider by name; all names use the compatible protocol."""
    del provider_name
    return OpenAIProvider(config)
