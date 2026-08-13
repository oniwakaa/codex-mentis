"""Provider base — abstract interface for LLM providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Iterator


@dataclass
class ProviderConfig:
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: Optional[int] = None
    timeout: float = 120.0
    max_retries: int = 3
    initial_backoff: float = 1.0
    backoff_factor: float = 2.0
    extra_params: Dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.token_usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    @abstractmethod
    def complete(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a chat completion. Returns {content, tool_calls, usage}."""
        ...

    def stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        """Stream response tokens. Default: falls back to complete()."""
        result = self.complete(messages)
        yield result.get("content", "")

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings. Default: raises NotImplementedError."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support embeddings")
