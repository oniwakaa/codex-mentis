import asyncio
import os
import json
import sqlite3
import unittest
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from codex_mentis.agents import BaseAgent, AgentResponse, ExplainerAgent, SelfImproverAgent, Orchestrator
from codex_mentis.agents.providers.base import BaseProvider, ProviderConfig
from codex_mentis.agents.providers import create_provider, get_provider, FallbackProvider

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
        return {"content": "Default Mock response", "tool_calls": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

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
        return {"content": "Default Mock response", "tool_calls": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    def stream(self, messages: List[Dict[str, str]]):
        yield "Default Mock stream chunk"

    async def astream(self, messages: List[Dict[str, str]]):
        yield "Default Mock stream chunk"

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

class TestCodexMentisAgents(unittest.TestCase):
    def setUp(self):
        self.prov = MockProvider()
        self.db_path = "/tmp/test_improver.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_base_agent_tool_validation(self):
        # 1. Test tool registration and json schema validation
        agent = BaseAgent(
            name="Validator",
            role="Tester",
            provider=self.prov,
            system_prompt="Test prompt"
        )
        
        # Register a simple math tool
        def add(a: int, b: int) -> int:
            return a + b
            
        agent.register_tool(
            "add",
            {
                "name": "add",
                "description": "Add two numbers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"}
                    },
                    "required": ["a", "b"]
                }
            },
            add
        )
        
        # Valid execution
        res = agent.with_tool("add", {"a": 5, "b": 10})
        self.assertEqual(res, 15)
        
        # Invalid execution (missing b)
        err = agent.with_tool("add", {"a": 5})
        self.assertIn("Validation failed", err)
        self.assertIn("Missing required property: 'b'", err)

        # Invalid execution (type mismatch)
        err2 = agent.with_tool("add", {"a": "not-an-int", "b": 10})
        self.assertIn("Validation failed", err2)
        self.assertIn("Property 'a': Expected integer", err2)

    def test_base_agent_history_management(self):
        agent = BaseAgent(
            name="HistoryMaker",
            role="Tester",
            provider=self.prov,
            system_prompt="Test system prompt",
            max_history_len=3
        )
        
        # Initially empty
        self.assertEqual(len(agent.get_history()), 0)
        
        # Add messages
        agent.add_message("user", "Hello 1")
        agent.add_message("assistant", "Hi 1")
        self.assertEqual(len(agent.get_history()), 2)
        
        # Exceed limit
        agent.add_message("user", "Hello 2")
        agent.add_message("assistant", "Hi 2")
        
        # History should be pruned to max_history_len (3)
        history = agent.get_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[-1]["content"], "Hi 2")
        self.assertEqual(history[0]["content"], "Hi 1")

    def test_base_agent_structured_output(self):
        class SimpleModel(BaseModel):
            answer: str
            confidence: float

        agent = BaseAgent(
            name="Structured",
            role="Tester",
            provider=self.prov,
            system_prompt="Test structured"
        )
        
        # Setup mock response containing valid JSON conforming to SimpleModel
        self.prov.responses.append({
            "content": '{"answer": "42", "confidence": 0.99}',
            "tool_calls": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10}
        })
        
        result = asyncio.run(agent.athink_structured("What is 42?", SimpleModel))
        self.assertEqual(result.answer, "42")
        self.assertEqual(result.confidence, 0.99)

    def test_fallback_provider(self):
        prov1 = MockProvider()
        prov2 = MockProvider()
        
        # Force prov1 to fail
        def raise_err(*args, **kwargs):
            raise ConnectionError("Endpoint down")
        prov1.complete = raise_err
        
        prov2.responses.append({
            "content": "Succeeded from secondary provider",
            "tool_calls": []
        })
        
        fallback = FallbackProvider([prov1, prov2])
        res = fallback.complete([{"role": "user", "content": "Hi"}])
        self.assertEqual(res["content"], "Succeeded from secondary provider")

    def test_self_improver_thompson_sampling(self):
        improver = SelfImproverAgent(self.prov, db_path=self.db_path)
        
        # Select strategy using Thompson Sampling
        strategies = ["socratic", "feynman"]
        chosen = improver.select_strategy(strategies)
        self.assertIn(chosen, strategies)
        
        # Track outcome (success for socratic)
        track_res = asyncio.run(
            improver.tool_track_outcome(prompt_id="socratic_v1", strategy_name="socratic", success=True, feedback="Good")
        )
        data = json.loads(track_res)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["new_alpha"], 2.0) # 1.0 + 1.0 success
        
        # Retrieve best prompt
        best_res = asyncio.run(improver.tool_get_best_prompt("socratic"))
        best_data = json.loads(best_res)
        self.assertEqual(best_data["prompt_id"], "socratic_v1")

    def test_explainer_agent_tools(self):
        explainer = ExplainerAgent(self.prov)
        
        self.prov.responses.append({
            "content": '{"concept": "gravity", "estimated_difficulty": "easy", "prerequisites": ["mass"], "key_cognitive_obstacles": ["spacetime"]}',
            "tool_calls": []
        })
        
        res = asyncio.run(explainer.tool_difficulty_assessor("gravity"))
        data = json.loads(res)
        self.assertEqual(data["concept"], "gravity")
        self.assertEqual(data["estimated_difficulty"], "easy")

    def test_orchestrator_parallel_reasoning(self):
        tutor = BaseAgent("Tutor", "Teacher", self.prov, "Tutor prompt")
        prover = BaseAgent("Prover", "Math expert", self.prov, "Prover prompt")
        
        self.prov.responses.extend([
            {"content": "Tutor explanation output", "tool_calls": []},
            {"content": "Prover derivation output", "tool_calls": []}
        ])
        
        orchestrator = Orchestrator(agents={"tutor": tutor, "prover": prover})
        
        res = asyncio.run(
            orchestrator.aprocess("Derive Lagrangian and explain it", mode="parallel_tutor_prover")
        )
        
        self.assertIn("Tutor explanation output", res.content)
        self.assertIn("Prover derivation output", res.content)

if __name__ == "__main__":
    unittest.main()
