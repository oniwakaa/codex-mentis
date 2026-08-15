"""Anthropic Claude provider implementation."""

from typing import Any

import httpx

from pitagora.agents.providers.base import BaseProvider


class AnthropicProvider(BaseProvider):
    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.config.api_key:
            headers["x-api-key"] = self.config.api_key
        return headers

    def _get_url(self) -> str:
        base = (self.config.base_url or "https://api.anthropic.com").rstrip("/")
        return f"{base}/v1/messages"

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        system_content = ""
        user_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_content += m.get("content", "") + "\n"
            else:
                user_messages.append(m)

        payload: dict[str, Any] = {
            "model": self.config.model or "claude-3-5-sonnet-20241022",
            "messages": user_messages,
            "max_tokens": self.config.max_tokens or 4096,
            "temperature": temperature,
        }
        if system_content.strip():
            payload["system"] = system_content.strip()

        with httpx.Client(timeout=self.config.httpx_timeout) as client:
            resp = client.post(self._get_url(), headers=self._get_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage_raw = data.get("usage", {})
        prompt_tokens = usage_raw.get("input_tokens", 0)
        completion_tokens = usage_raw.get("output_tokens", 0)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        self._record_usage(usage)
        return {"content": content, "tool_calls": [], "usage": usage}
