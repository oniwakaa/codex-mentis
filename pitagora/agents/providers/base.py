"""Provider base — abstract interface for LLM providers."""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class ProviderConfig:
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    max_tokens: int | None = None
    timeout: float | httpx.Timeout = 120.0
    connect_timeout: float | None = None
    read_timeout: float | None = None
    write_timeout: float | None = None
    pool_timeout: float | None = None
    max_retries: int = 3
    initial_backoff: float = 1.0
    backoff_factor: float = 2.0
    prompt_token_cost: float = 0.0
    completion_token_cost: float = 0.0
    extra_params: dict[str, Any] = field(default_factory=dict)

    @property
    def httpx_timeout(self) -> float | httpx.Timeout:
        """Return the legacy float or an httpx timeout with phase overrides."""
        phases = (
            self.connect_timeout,
            self.read_timeout,
            self.write_timeout,
            self.pool_timeout,
        )
        if all(value is None for value in phases):
            return self.timeout

        if isinstance(self.timeout, httpx.Timeout):
            defaults = (
                self.timeout.connect,
                self.timeout.read,
                self.timeout.write,
                self.timeout.pool,
            )
        else:
            defaults = (self.timeout,) * 4
        connect, read, write, pool = (
            override if override is not None else default
            for override, default in zip(phases, defaults, strict=False)
        )
        return httpx.Timeout(connect=connect, read=read, write=write, pool=pool)


class BaseProvider(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.token_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self.total_cost = 0.0

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a chat completion. Returns {content, tool_calls, usage}."""
        ...

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a completion without blocking the event loop."""
        return await asyncio.to_thread(
            self.complete,
            messages,
            tools,
            temperature,
            response_format,
        )

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        """Stream response tokens. Default: falls back to complete()."""
        result = self.complete(messages)
        yield result.get("content", "")

    async def astream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Stream asynchronously. Default: falls back to acomplete()."""
        result = await self.acomplete(messages)
        yield result.get("content", "")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings. Default: raises NotImplementedError."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support embeddings")

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings without blocking the event loop."""
        return await asyncio.to_thread(self.embed, texts)

    def _record_usage(
        self,
        usage: Mapping[str, int],
        *,
        config: ProviderConfig | None = None,
    ) -> None:
        prompt_tokens = usage["prompt_tokens"]
        completion_tokens = usage["completion_tokens"]
        self.token_usage["prompt_tokens"] += prompt_tokens
        self.token_usage["completion_tokens"] += completion_tokens
        self.token_usage["total_tokens"] += usage["total_tokens"]

        rates = config or self.config
        self.total_cost += (
            prompt_tokens * rates.prompt_token_cost
            + completion_tokens * rates.completion_token_cost
        )
