"""LM Studio provider implementation (OpenAI-compatible local server)."""

from pitagora.agents.providers.openai import OpenAIProvider


class LMStudioProvider(OpenAIProvider):
    def _get_url(self, endpoint: str = "chat/completions") -> str:
        base = (self.config.base_url or "http://localhost:1234/v1").rstrip("/")
        return f"{base}/{endpoint}"
