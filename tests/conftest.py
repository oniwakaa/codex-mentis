import matplotlib
matplotlib.use('Agg')
import pytest
import os
import shutil
from typing import List, Dict, Any, Optional, AsyncIterator, Iterator
from codex_mentis.agents.providers.base import BaseProvider, ProviderConfig

class MockProvider(BaseProvider):
    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config or ProviderConfig(api_key="mock", model="mock-model"))
        self.responses: List[Dict[str, Any]] = []
        self.call_history: List[Dict[str, Any]] = []

    def complete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.call_history.append({"messages": messages, "tools": tools, "response_format": response_format})
        if self.responses:
            return self.responses.pop(0)
        return {"content": "Default Mock response", "tool_calls": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}

    async def acomplete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.call_history.append({"messages": messages, "tools": tools, "response_format": response_format})
        if self.responses:
            return self.responses.pop(0)
        return {"content": "Default Mock response", "tool_calls": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}

    def stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        yield "Default Mock stream chunk"

    async def astream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        yield "Default Mock stream chunk"

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [[0.1] * 384 for _ in texts]

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        return [[0.1] * 384 for _ in texts]

@pytest.fixture
def mock_provider():
    return MockProvider()

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_codex_mentis.db"
    return str(db_file)

@pytest.fixture
def temp_yaml(tmp_path):
    yaml_file = tmp_path / "concepts.yaml"
    content = """
Calculus:
  description: "Study of continuous change"
  prerequisites: []
Linear Algebra:
  description: "Study of vectors and linear fields"
  prerequisites: []
Classical Mechanics:
  description: "Study of motion of macroscopic objects"
  prerequisites: ["Calculus", "Linear Algebra"]
Quantum Mechanics:
  description: "Study of particles at the atomic scale"
  prerequisites: ["Calculus", "Linear Algebra", "Classical Mechanics"]
"""
    yaml_file.write_text(content)
    return str(yaml_file)
