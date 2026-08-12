import json
import logging
from typing import Dict, Any, List, Optional, AsyncIterator, Iterator
import httpx

from codex_mentis.agents.providers.base import BaseProvider, ProviderConfig

logger = logging.getLogger(__name__)

class AnthropicProvider(BaseProvider):
    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key or "",
            "anthropic-version": "2023-06-01"
        }
        return headers

    def _get_url(self) -> str:
        return self.config.base_url or "https://api.anthropic.com/v1/messages"

    def _prepare_payload(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        stream: bool = False
    ) -> Dict[str, Any]:
        system_content = None
        formatted_messages = []
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            # Format system message separately
            if role == "system":
                system_content = content
            else:
                # Handle structured content (e.g. lists for vision/tools)
                if isinstance(content, (list, dict)):
                    formatted_messages.append({
                        "role": role,
                        "content": content
                    })
                else:
                    formatted_messages.append({
                        "role": role,
                        "content": content or ""
                    })

        payload: Dict[str, Any] = {
            "model": self.config.model or "claude-3-5-sonnet-20240620",
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": self.config.max_tokens or 4096,
            "stream": stream
        }

        if system_content:
            payload["system"] = system_content

        if tools:
            anthropic_tools = []
            for tool in tools:
                if tool.get("type") == "function":
                    func = tool.get("function", {})
                    anthropic_tools.append({
                        "name": func.get("name"),
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {"type": "object", "properties": {}})
                    })
                else:
                    anthropic_tools.append(tool)
            payload["tools"] = anthropic_tools

        # Merge extra params
        if self.config.extra_params:
            for k, v in self.config.extra_params.items():
                payload[k] = v

        return payload

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        content_parts = []
        tool_calls = []
        
        for block in data.get("content", []):
            if block.get("type") == "text":
                content_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "name": block.get("name"),
                    "arguments": block.get("input", {})
                })

        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        
        return {
            "content": "".join(content_parts),
            "tool_calls": tool_calls,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }

    def complete(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = self._get_url()
        headers = self._get_headers()
        payload = self._prepare_payload(messages, tools, temperature, stream=False)

        with httpx.Client(timeout=self.config.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        parsed = self._parse_response(data)
        
        # Accumulate tokens
        usage = parsed["usage"]
        self.token_usage["prompt_tokens"] += usage["prompt_tokens"]
        self.token_usage["completion_tokens"] += usage["completion_tokens"]
        self.token_usage["total_tokens"] += usage["total_tokens"]
        
        return parsed

    async def acomplete(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = self._get_url()
        headers = self._get_headers()
        payload = self._prepare_payload(messages, tools, temperature, stream=False)

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        parsed = self._parse_response(data)
        
        # Accumulate tokens
        usage = parsed["usage"]
        self.token_usage["prompt_tokens"] += usage["prompt_tokens"]
        self.token_usage["completion_tokens"] += usage["completion_tokens"]
        self.token_usage["total_tokens"] += usage["total_tokens"]
        
        return parsed

    def stream(self, messages: List[Dict[str, Any]]) -> Iterator[str]:
        url = self._get_url()
        headers = self._get_headers()
        payload = self._prepare_payload(messages, stream=True)

        with httpx.Client(timeout=self.config.timeout) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            chunk = json.loads(data_str)
                            if chunk.get("type") == "content_block_delta":
                                delta = chunk.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield delta.get("text", "")
                        except Exception:
                            continue

    async def astream(self, messages: List[Dict[str, Any]]) -> AsyncIterator[str]:
        url = self._get_url()
        headers = self._get_headers()
        payload = self._prepare_payload(messages, stream=True)

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            chunk = json.loads(data_str)
                            if chunk.get("type") == "content_block_delta":
                                delta = chunk.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield delta.get("text", "")
                        except Exception:
                            continue

    def embed(self, texts: List[str]) -> List[List[float]]:
        # Anthropic does not support text embeddings natively yet.
        raise NotImplementedError("Anthropic does not natively support an embeddings endpoint.")

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        # Anthropic does not support text embeddings natively yet.
        raise NotImplementedError("Anthropic does not natively support an embeddings endpoint.")
