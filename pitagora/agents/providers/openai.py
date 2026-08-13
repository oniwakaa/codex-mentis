import json
import logging
import time
import asyncio
from typing import Dict, Any, List, Optional, AsyncIterator, Iterator
import httpx

from pitagora.agents.providers.base import BaseProvider, ProviderConfig

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseProvider):
    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json"
        }
        if self.config.api_key and self.config.api_key != "mock":
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _get_url(self, endpoint: str = "chat/completions") -> str:
        base = self.config.base_url or "https://api.openai.com/v1"
        base = base.rstrip("/")
        return f"{base}/{endpoint}"

    def _build_payload(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.config.model or "gpt-4o",
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        if self.config.max_tokens:
            payload["max_tokens"] = self.config.max_tokens
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["response_format"] = response_format
        
        # Merge extra params
        if self.config.extra_params:
            for k, v in self.config.extra_params.items():
                payload[k] = v
        return payload

    def _parse_response_choice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        
        tool_calls = []
        raw_tool_calls = message.get("tool_calls") or []
        for tc in raw_tool_calls:
            if tc.get("type") == "function":
                func = tc.get("function", {})
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except Exception:
                    args = func.get("arguments", {})
                tool_calls.append({
                    "name": func.get("name"),
                    "arguments": args
                })
        
        usage = data.get("usage", {})
        
        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            }
        }

    def complete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = self._get_url()
        headers = self._get_headers()
        payload = self._build_payload(messages, tools, temperature, response_format, stream=False)

        # Retry rate limits and server errors only
        retries = self.config.max_retries
        backoff = self.config.initial_backoff
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=self.config.timeout) as client:
                    response = client.post(url, headers=headers, json=payload)
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt == retries:
                            response.raise_for_status()
                        time.sleep(backoff)
                        backoff *= self.config.backoff_factor
                        continue
                    response.raise_for_status()
                    data = response.json()
                    parsed = self._parse_response_choice(data)

                    # Accumulate token usage
                    usage = parsed["usage"]
                    self.token_usage["prompt_tokens"] += usage["prompt_tokens"]
                    self.token_usage["completion_tokens"] += usage["completion_tokens"]
                    self.token_usage["total_tokens"] += usage["total_tokens"]

                    return parsed
            except httpx.HTTPStatusError:
                raise
            except (httpx.TransportError, httpx.TimeoutException, OSError) as e:
                if attempt == retries:
                    raise e
                time.sleep(backoff)
                backoff *= self.config.backoff_factor

        raise RuntimeError("Failed to complete request due to unexpected errors.")

    async def acomplete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = self._get_url()
        headers = self._get_headers()
        payload = self._build_payload(messages, tools, temperature, response_format, stream=False)

        retries = self.config.max_retries
        backoff = self.config.initial_backoff
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt == retries:
                            response.raise_for_status()
                        await asyncio.sleep(backoff)
                        backoff *= self.config.backoff_factor
                        continue
                    response.raise_for_status()
                    data = response.json()
                    parsed = self._parse_response_choice(data)

                    # Accumulate token usage
                    usage = parsed["usage"]
                    self.token_usage["prompt_tokens"] += usage["prompt_tokens"]
                    self.token_usage["completion_tokens"] += usage["completion_tokens"]
                    self.token_usage["total_tokens"] += usage["total_tokens"]

                    return parsed
            except httpx.HTTPStatusError:
                raise
            except (httpx.TransportError, httpx.TimeoutException, OSError) as e:
                if attempt == retries:
                    raise e
                await asyncio.sleep(backoff)
                backoff *= self.config.backoff_factor

        raise RuntimeError("Failed to complete request due to unexpected errors.")

    def stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        url = self._get_url()
        headers = self._get_headers()
        payload = self._build_payload(messages, stream=True)

        with httpx.Client(timeout=self.config.timeout) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            choice = chunk.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except Exception:
                            continue

    async def astream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        url = self._get_url()
        headers = self._get_headers()
        payload = self._build_payload(messages, stream=True)

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            choice = chunk.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except Exception:
                            continue

    def embed(self, texts: List[str]) -> List[List[float]]:
        url = self._get_url("embeddings")
        headers = self._get_headers()
        payload = {
            "model": self.config.extra_params.get("embedding_model", "text-embedding-3-small"),
            "input": texts
        }

        with httpx.Client(timeout=self.config.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
        embeddings = [item["embedding"] for item in data.get("data", [])]
        return embeddings

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        url = self._get_url("embeddings")
        headers = self._get_headers()
        payload = {
            "model": self.config.extra_params.get("embedding_model", "text-embedding-3-small"),
            "input": texts
        }

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
        embeddings = [item["embedding"] for item in data.get("data", [])]
        return embeddings
