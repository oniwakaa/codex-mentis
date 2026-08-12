from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, AsyncIterator, Iterator

@dataclass
class ProviderConfig:
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: Optional[int] = None
    timeout: float = 60.0
    max_retries: int = 3
    initial_backoff: float = 1.0
    backoff_factor: float = 2.0
    extra_params: Dict[str, Any] = field(default_factory=dict)

class BaseProvider(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

    def reset_token_usage(self):
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

    def get_token_usage(self) -> Dict[str, int]:
        return self.token_usage

    @abstractmethod
    def complete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a chat completion request synchronously.
        Returns a dict containing:
          - "content": str
          - "tool_calls": List[Dict[str, Any]] (each with "name" and "arguments")
          - "usage": Optional[Dict[str, int]] (with keys "prompt_tokens", "completion_tokens", "total_tokens")
        """
        pass

    @abstractmethod
    async def acomplete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a chat completion request asynchronously.
        Returns a dict containing:
          - "content": str
          - "tool_calls": List[Dict[str, Any]] (each with "name" and "arguments")
          - "usage": Optional[Dict[str, int]] (with keys "prompt_tokens", "completion_tokens", "total_tokens")
        """
        pass

    @abstractmethod
    def stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        """
        Stream back response text tokens synchronously.
        """
        pass

    @abstractmethod
    async def astream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """
        Stream back response text tokens asynchronously.
        """
        pass

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings synchronously for the list of texts.
        """
        pass

    @abstractmethod
    async def aembed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings asynchronously for the list of texts.
        """
        pass
