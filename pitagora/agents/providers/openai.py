"""OpenAI-compatible HTTP provider."""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from pitagora.agents.providers.base import BaseProvider

TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class OpenAIProvider(BaseProvider):
    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key and self.config.api_key != "mock":
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _get_url(self, endpoint: str = "chat/completions") -> str:
        base = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        return f"{base}/{endpoint}"

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model or "gpt-4o",
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if self.config.max_tokens:
            payload["max_tokens"] = self.config.max_tokens
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["response_format"] = response_format
        payload.update(self.config.extra_params)
        return payload

    @staticmethod
    def _decode_response(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("OpenAI response was not valid JSON") from error
        if not isinstance(data, dict):
            raise ValueError("OpenAI response JSON must be an object")
        return data

    def _parse_response_choice(self, data: dict[str, Any]) -> dict[str, Any]:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("OpenAI response must contain a non-empty choices list")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ValueError("OpenAI response choice must be an object")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("OpenAI response choice must contain a message object")

        content = message.get("content")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            raise ValueError("OpenAI response message content must be a string or null")

        raw_tool_calls = message.get("tool_calls", [])
        if raw_tool_calls is None:
            raw_tool_calls = []
        if not isinstance(raw_tool_calls, list):
            raise ValueError("OpenAI response tool calls must be a list")

        tool_calls: list[dict[str, Any]] = []
        for index, tool_call in enumerate(raw_tool_calls):
            if not isinstance(tool_call, dict) or tool_call.get("type") != "function":
                raise ValueError(f"OpenAI response tool call {index} must be a function")
            function = tool_call.get("function")
            if not isinstance(function, dict):
                raise ValueError(f"OpenAI response tool call {index} must contain a function")
            name = function.get("name")
            arguments_json = function.get("arguments")
            if not isinstance(name, str) or not name:
                raise ValueError(f"OpenAI response tool call {index} must have a name")
            if not isinstance(arguments_json, str):
                raise ValueError(
                    f"OpenAI response tool call {index} arguments must be a JSON string"
                )
            try:
                arguments = json.loads(arguments_json)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"OpenAI response tool call {index} arguments are not valid JSON"
                ) from error
            if not isinstance(arguments, dict):
                raise ValueError(
                    f"OpenAI response tool call {index} arguments must decode to an object"
                )
            tool_calls.append({"name": name, "arguments": arguments})

        raw_usage = data.get("usage", {})
        if not isinstance(raw_usage, dict):
            raise ValueError("OpenAI response usage must be an object")
        usage: dict[str, int] = {}
        for key in ("prompt_tokens", "completion_tokens"):
            value = raw_usage.get(key, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"OpenAI response usage {key} must be a non-negative integer")
            usage[key] = value
        total_tokens = raw_usage.get(
            "total_tokens",
            usage["prompt_tokens"] + usage["completion_tokens"],
        )
        if not isinstance(total_tokens, int) or isinstance(total_tokens, bool) or total_tokens < 0:
            raise ValueError("OpenAI response usage total_tokens must be a non-negative integer")
        usage["total_tokens"] = total_tokens

        return {"content": content, "tool_calls": tool_calls, "usage": usage}

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._build_payload(
            messages,
            tools,
            temperature,
            response_format,
            stream=False,
        )
        backoff = self.config.initial_backoff
        for attempt in range(self.config.max_retries + 1):
            try:
                with httpx.Client(timeout=self.config.httpx_timeout) as client:
                    response = client.post(
                        self._get_url(),
                        headers=self._get_headers(),
                        json=payload,
                    )
                if response.status_code in TRANSIENT_STATUS_CODES:
                    if attempt == self.config.max_retries:
                        response.raise_for_status()
                    time.sleep(backoff)
                    backoff *= self.config.backoff_factor
                    continue
                response.raise_for_status()
            except httpx.HTTPStatusError:
                raise
            except httpx.TransportError:
                if attempt == self.config.max_retries:
                    raise
                time.sleep(backoff)
                backoff *= self.config.backoff_factor
                continue

            parsed = self._parse_response_choice(self._decode_response(response))
            self._record_usage(parsed["usage"])
            return parsed

        raise RuntimeError("OpenAI request retry loop exhausted unexpectedly")

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._build_payload(
            messages,
            tools,
            temperature,
            response_format,
            stream=False,
        )
        backoff = self.config.initial_backoff
        for attempt in range(self.config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.httpx_timeout) as client:
                    response = await client.post(
                        self._get_url(),
                        headers=self._get_headers(),
                        json=payload,
                    )
                if response.status_code in TRANSIENT_STATUS_CODES:
                    if attempt == self.config.max_retries:
                        response.raise_for_status()
                    await asyncio.sleep(backoff)
                    backoff *= self.config.backoff_factor
                    continue
                response.raise_for_status()
            except httpx.HTTPStatusError:
                raise
            except httpx.TransportError:
                if attempt == self.config.max_retries:
                    raise
                await asyncio.sleep(backoff)
                backoff *= self.config.backoff_factor
                continue

            parsed = self._parse_response_choice(self._decode_response(response))
            self._record_usage(parsed["usage"])
            return parsed

        raise RuntimeError("OpenAI request retry loop exhausted unexpectedly")

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        payload = self._build_payload(messages, stream=True)
        with httpx.Client(timeout=self.config.httpx_timeout) as client:
            with client.stream(
                "POST",
                self._get_url(),
                headers=self._get_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_json = line[6:]
                    if data_json == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_json)
                        content = chunk["choices"][0]["delta"].get("content")
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
                    if content:
                        yield content

    async def astream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        payload = self._build_payload(messages, stream=True)
        async with httpx.AsyncClient(timeout=self.config.httpx_timeout) as client:
            async with client.stream(
                "POST",
                self._get_url(),
                headers=self._get_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_json = line[6:]
                    if data_json == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_json)
                        content = chunk["choices"][0]["delta"].get("content")
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
                    if content:
                        yield content

    async def stream_completion(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream completion events from OpenAI streaming API."""
        payload = self._build_payload(messages, tools=tools, stream=True)
        async with httpx.AsyncClient(timeout=self.config.httpx_timeout) as client:
            async with client.stream(
                "POST",
                self._get_url(),
                headers=self._get_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_json = line[6:]
                    if data_json == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_json)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content")
                        tool_calls = delta.get("tool_calls")
                        if content:
                            yield {"type": "token", "content": content}
                        if tool_calls:
                            yield {"type": "tool_call", "content": tool_calls}
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue

        yield {"type": "done", "content": {}}

    def embed(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "model": self.config.extra_params.get(
                "embedding_model",
                "text-embedding-3-small",
            ),
            "input": texts,
        }
        with httpx.Client(timeout=self.config.httpx_timeout) as client:
            response = client.post(
                self._get_url("embeddings"),
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
        data = self._decode_response(response)
        raw_embeddings = data.get("data")
        if not isinstance(raw_embeddings, list):
            raise ValueError("OpenAI embeddings response must contain a data list")
        try:
            return [item["embedding"] for item in raw_embeddings]
        except (KeyError, TypeError) as error:
            raise ValueError("OpenAI embeddings response contains an invalid item") from error

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "model": self.config.extra_params.get(
                "embedding_model",
                "text-embedding-3-small",
            ),
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=self.config.httpx_timeout) as client:
            response = await client.post(
                self._get_url("embeddings"),
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
        data = self._decode_response(response)
        raw_embeddings = data.get("data")
        if not isinstance(raw_embeddings, list):
            raise ValueError("OpenAI embeddings response must contain a data list")
        try:
            return [item["embedding"] for item in raw_embeddings]
        except (KeyError, TypeError) as error:
            raise ValueError("OpenAI embeddings response contains an invalid item") from error
