from typing import Any

import httpx
import pytest

import pitagora.agents.providers.openai as openai_module
from pitagora.agents.providers import (
    FallbackProvider,
    create_provider,
    get_provider,
)
from pitagora.agents.providers.base import BaseProvider, ProviderConfig
from pitagora.agents.providers.openai import OpenAIProvider
from tests.conftest import MockProvider

MESSAGES = [{"role": "user", "content": "hello"}]


def _completion_response(
    status_code: int = 200,
    *,
    content: bytes | None = None,
    usage: dict[str, int] | None = None,
) -> httpx.Response:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    if content is not None:
        return httpx.Response(status_code, content=content, request=request)
    return httpx.Response(
        status_code,
        json={
            "choices": [{"message": {"content": "ok", "tool_calls": []}}],
            "usage": usage
            or {
                "prompt_tokens": 2,
                "completion_tokens": 3,
                "total_tokens": 5,
            },
        },
        request=request,
    )


def _install_sync_client(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: list[httpx.Response | Exception],
) -> tuple[list[float | httpx.Timeout], list[float], list[None]]:
    remaining = iter(outcomes)
    timeouts: list[float | httpx.Timeout] = []
    sleeps: list[float] = []
    calls: list[None] = []

    class Client:
        def __init__(self, *, timeout: float | httpx.Timeout) -> None:
            timeouts.append(timeout)

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, *args: Any, **kwargs: Any) -> httpx.Response:
            calls.append(None)
            outcome = next(remaining)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    monkeypatch.setattr(openai_module.httpx, "Client", Client)
    monkeypatch.setattr(openai_module.time, "sleep", sleeps.append)
    return timeouts, sleeps, calls


def _install_async_client(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: list[httpx.Response | Exception],
) -> tuple[list[float | httpx.Timeout], list[float], list[None]]:
    remaining = iter(outcomes)
    timeouts: list[float | httpx.Timeout] = []
    sleeps: list[float] = []
    calls: list[None] = []

    class AsyncClient:
        def __init__(self, *, timeout: float | httpx.Timeout) -> None:
            timeouts.append(timeout)

        async def __aenter__(self) -> "AsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: Any, **kwargs: Any) -> httpx.Response:
            calls.append(None)
            outcome = next(remaining)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(openai_module.httpx, "AsyncClient", AsyncClient)
    monkeypatch.setattr(openai_module.asyncio, "sleep", sleep)
    return timeouts, sleeps, calls


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


def test_timeout_config_preserves_float_and_supports_phase_overrides():
    assert ProviderConfig(timeout=7.5).httpx_timeout == 7.5

    timeout = ProviderConfig(
        timeout=30.0,
        connect_timeout=1.0,
        read_timeout=2.0,
        write_timeout=3.0,
        pool_timeout=4.0,
    ).httpx_timeout

    assert isinstance(timeout, httpx.Timeout)
    assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (1.0, 2.0, 3.0, 4.0)


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_complete_retries_exact_transient_statuses(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
):
    _, sleeps, calls = _install_sync_client(
        monkeypatch,
        [_completion_response(status_code), _completion_response()],
    )
    provider = OpenAIProvider(
        ProviderConfig(max_retries=1, initial_backoff=0.25, backoff_factor=2.0)
    )

    assert provider.complete(MESSAGES)["content"] == "ok"
    assert len(calls) == 2
    assert sleeps == [0.25]


@pytest.mark.parametrize("status_code", [400, 501, 505])
def test_complete_does_not_retry_other_http_statuses(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
):
    _, sleeps, calls = _install_sync_client(
        monkeypatch,
        [_completion_response(status_code), _completion_response()],
    )
    provider = OpenAIProvider(ProviderConfig(max_retries=1))

    with pytest.raises(httpx.HTTPStatusError):
        provider.complete(MESSAGES)

    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout])
def test_complete_retries_transport_and_timeout_errors(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[httpx.TransportError],
):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    _, sleeps, calls = _install_sync_client(
        monkeypatch,
        [error_type("temporary failure", request=request), _completion_response()],
    )
    provider = OpenAIProvider(ProviderConfig(max_retries=1, initial_backoff=0.5))

    assert provider.complete(MESSAGES)["content"] == "ok"
    assert len(calls) == 2
    assert sleeps == [0.5]


@pytest.mark.parametrize("first_failure", [429, httpx.ConnectError])
async def test_acomplete_has_the_same_retry_policy(
    monkeypatch: pytest.MonkeyPatch,
    first_failure: int | type[httpx.TransportError],
):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    failure: httpx.Response | Exception
    if isinstance(first_failure, int):
        failure = _completion_response(first_failure)
    else:
        failure = first_failure("temporary failure", request=request)
    _, sleeps, calls = _install_async_client(
        monkeypatch,
        [failure, _completion_response()],
    )
    provider = OpenAIProvider(ProviderConfig(max_retries=1, initial_backoff=0.75))

    assert (await provider.acomplete(MESSAGES))["content"] == "ok"
    assert len(calls) == 2
    assert sleeps == [0.75]


def test_complete_passes_configured_timeout_phases(monkeypatch: pytest.MonkeyPatch):
    timeouts, _, _ = _install_sync_client(monkeypatch, [_completion_response()])
    provider = OpenAIProvider(ProviderConfig(timeout=30.0, connect_timeout=1.0, read_timeout=9.0))

    provider.complete(MESSAGES)

    timeout = timeouts[0]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 1.0
    assert timeout.read == 9.0
    assert timeout.write == 30.0
    assert timeout.pool == 30.0


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"choices": []},
        {"choices": [{"message": "not an object"}]},
        {"choices": [{"message": {"content": 42}}]},
        {"choices": [{"message": {"content": "ok"}}], "usage": "invalid"},
    ],
)
def test_response_validation_rejects_malformed_shapes(data: dict[str, Any]):
    provider = OpenAIProvider(ProviderConfig())

    with pytest.raises(ValueError, match="response"):
        provider._parse_response_choice(data)


def test_complete_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch):
    _install_sync_client(monkeypatch, [_completion_response(content=b"{not-json")])
    provider = OpenAIProvider(ProviderConfig())

    with pytest.raises(ValueError, match="JSON"):
        provider.complete(MESSAGES)


@pytest.mark.parametrize(
    "tool_call",
    [
        {"type": "function", "function": {"name": "", "arguments": "{}"}},
        {"type": "function", "function": {"name": "search", "arguments": "not-json"}},
        {"type": "function", "function": {"name": "search", "arguments": "[]"}},
        {"type": "custom", "function": {"name": "search", "arguments": "{}"}},
    ],
)
def test_tool_call_validation_rejects_malformed_calls(tool_call: dict[str, Any]):
    provider = OpenAIProvider(ProviderConfig())
    data = {
        "choices": [{"message": {"content": None, "tool_calls": [tool_call]}}],
        "usage": {},
    }

    with pytest.raises(ValueError, match="tool call"):
        provider._parse_response_choice(data)


def test_tool_call_arguments_are_strictly_decoded():
    provider = OpenAIProvider(ProviderConfig())
    result = provider._parse_response_choice(
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"query": "Euler"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {},
        }
    )

    assert result["tool_calls"] == [{"name": "search", "arguments": {"query": "Euler"}}]


async def test_usage_and_cost_accumulate_across_sync_and_async_calls(
    monkeypatch: pytest.MonkeyPatch,
):
    config = ProviderConfig(prompt_token_cost=0.01, completion_token_cost=0.02)
    provider = OpenAIProvider(config)
    _install_sync_client(
        monkeypatch,
        [
            _completion_response(
                usage={"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}
            )
        ],
    )
    provider.complete(MESSAGES)
    _install_async_client(
        monkeypatch,
        [
            _completion_response(
                usage={"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}
            )
        ],
    )

    await provider.acomplete(MESSAGES)

    assert provider.token_usage == {
        "prompt_tokens": 7,
        "completion_tokens": 10,
        "total_tokens": 17,
    }
    assert provider.total_cost == pytest.approx(0.27)


def test_token_cost_defaults_to_zero(monkeypatch: pytest.MonkeyPatch):
    _install_sync_client(monkeypatch, [_completion_response()])
    provider = OpenAIProvider(ProviderConfig())

    provider.complete(MESSAGES)

    assert provider.total_cost == 0.0


class _FailingAsyncProvider(MockProvider):
    async def acomplete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise ValueError("unavailable")


class _FailingAsyncStreamProvider(MockProvider):
    async def astream(self, messages: list[dict[str, str]]):
        raise ValueError("unavailable")
        yield ""


async def test_fallback_acomplete_uses_next_provider_and_accounts_usage():
    first = _FailingAsyncProvider()
    second = MockProvider(ProviderConfig(prompt_token_cost=0.01, completion_token_cost=0.02))
    second.responses.append(
        {
            "content": "fallback",
            "tool_calls": [],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }
    )
    fallback = FallbackProvider([first, second])

    result = await fallback.acomplete(MESSAGES)

    assert result["content"] == "fallback"
    assert fallback.token_usage == {
        "prompt_tokens": 2,
        "completion_tokens": 3,
        "total_tokens": 5,
    }
    assert fallback.total_cost == pytest.approx(0.08)


async def test_fallback_astream_catches_errors_raised_during_iteration():
    fallback = FallbackProvider([_FailingAsyncStreamProvider(), MockProvider()])

    chunks = [chunk async for chunk in fallback.astream(MESSAGES)]

    assert chunks == ["Default Mock stream chunk"]
