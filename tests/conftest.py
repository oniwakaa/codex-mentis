import matplotlib

matplotlib.use("Agg")
import os
import shutil
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

from pitagora.agents.providers.base import BaseProvider, ProviderConfig


class MockProvider(BaseProvider):
    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config or ProviderConfig(api_key="mock", model="mock-model"))
        self.responses: list[dict[str, Any]] = []
        self.call_history: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.call_history.append(
            {"messages": messages, "tools": tools, "response_format": response_format}
        )
        if self.responses:
            return self.responses.pop(0)
        return {
            "content": "Default Mock response",
            "tool_calls": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.call_history.append(
            {"messages": messages, "tools": tools, "response_format": response_format}
        )
        if self.responses:
            return self.responses.pop(0)
        return {
            "content": "Default Mock response",
            "tool_calls": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        yield "Default Mock stream chunk"

    async def astream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        yield "Default Mock stream chunk"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]


@pytest.fixture
def mock_provider():
    return MockProvider()


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_pitagora.db"
    return str(db_file)


@pytest.fixture
def temp_yaml(tmp_path):
    yaml_file = tmp_path / "concepts.yaml"
    content = """
General:
  - id: Calculus
    name: Calculus
    prerequisites: []
  - id: Linear Algebra
    name: Linear Algebra
    prerequisites: []
  - id: Classical Mechanics
    name: Classical Mechanics
    prerequisites: [Calculus, Linear Algebra]
  - id: Quantum Mechanics
    name: Quantum Mechanics
    prerequisites: [Calculus, Linear Algebra, Classical Mechanics]
"""
    yaml_file.write_text(content)
    return str(yaml_file)
