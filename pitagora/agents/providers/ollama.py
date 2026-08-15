"""Local Ollama provider implementation."""

from typing import Any

import httpx

from pitagora.agents.providers.base import BaseProvider


class OllamaProvider(BaseProvider):
    def _get_url(self) -> str:
        base = (self.config.base_url or "http://localhost:11434").rstrip("/")
        return f"{base}/api/chat"

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "model": self.config.model or "llama3",
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        with httpx.Client(timeout=self.config.httpx_timeout) as client:
            resp = client.post(self._get_url(), json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        self._record_usage(usage)
        return {"content": content, "tool_calls": [], "usage": usage}
