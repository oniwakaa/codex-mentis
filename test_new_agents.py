import asyncio
import os
import json
import sqlite3
import unittest
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from pitagora.agents import BaseAgent, AgentResponse, ExplainerAgent, SelfImproverAgent, Orchestrator
from pitagora.agents.providers.base import BaseProvider, ProviderConfig
from pitagora.agents.providers import create_provider, get_provider, FallbackProvider

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

    def test_knowledge_graph(self):
        from pitagora.memory.knowledge_graph import KnowledgeGraph, EntityNode, Relationship
        db_file = "/tmp/test_kg.db"
        if os.path.exists(db_file):
            os.remove(db_file)
        kg = KnowledgeGraph(db_path=db_file)
        
        try:
            # 1. Add entity
            e1_id = kg.add_entity("Lagrangian Mechanics", "Concept", {"difficulty": "challenging"})
            e2_id = kg.add_entity("Action Principle", "Concept", {"difficulty": "moderate"})
            
            self.assertEqual(e1_id, "lagrangian_mechanics")
            self.assertEqual(e2_id, "action_principle")
            
            # 2. Find entity
            e1 = kg.find_entity("Lagrangian Mechanics")
            self.assertIsNotNone(e1)
            self.assertEqual(e1.name, "Lagrangian Mechanics")
            self.assertEqual(e1.properties["difficulty"], "challenging")
            
            # 3. Add relationship
            kg.add_relationship("Action Principle", "Lagrangian Mechanics", "prerequisite_of", {"weight": 1.0})
            
            # 4. Find related
            related = kg.find_related("Action Principle", depth=1)
            self.assertEqual(len(related), 1)
            self.assertEqual(related[0][0].name, "Lagrangian Mechanics")
            self.assertEqual(related[0][1].rel_type, "prerequisite_of")
            
            # 5. Semantic Search
            matches = kg.semantic_search("Lagrangian", limit=1)
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].id, "lagrangian_mechanics")
            
            # 6. Graph traversal
            subgraph = kg.graph_traversal("Action Principle", max_depth=1)
            self.assertEqual(len(subgraph["nodes"]), 2)
            self.assertEqual(len(subgraph["relationships"]), 1)
            
            # 7. Merge entities
            e3_id = kg.add_entity("Lagrange Formalism", "Concept", {"alternate": "yes"})
            kg.add_relationship("Lagrange Formalism", "Action Principle", "related_to")
            merged_id = kg.merge_entities("lagrangian_mechanics", "lagrange_formalism")
            self.assertEqual(merged_id, "lagrangian_mechanics")
            
            # The merged relationship should now point to lagrangian_mechanics
            related_merged = kg.find_related("Action Principle", depth=1)
            self.assertEqual(len(related_merged), 2)
            
            # 8. Context window
            context_str = kg.get_context_window("lagrangian_mechanics")
            self.assertIn("Lagrangian Mechanics", context_str)
            
            # 9. Temporal Query
            temporal = kg.temporal_query("lagrangian_mechanics")
            self.assertTrue(len(temporal) > 0)
            
            # 10. Improve weight
            kg.improve("lagrangian_mechanics", "positive test feedback", 0.5)
            traversed = kg.find_related("lagrangian_mechanics", depth=1)
            self.assertTrue(any(r[1].weight > 1.0 for r in traversed))

            # 11. Forget
            kg.forget("action_principle")
            self.assertIsNone(kg.find_entity("action_principle"))
            
        finally:
            if os.path.exists(db_file):
                os.remove(db_file)

    def test_knowledge_graph_remember_recall(self):
        from pitagora.memory.knowledge_graph import KnowledgeGraph
        db_file = "/tmp/test_kg_rr.db"
        if os.path.exists(db_file):
            os.remove(db_file)
        kg = KnowledgeGraph(db_path=db_file)
        
        try:
            agent = BaseAgent("TestAgent", "Tester", self.prov, "Mock prompt")
            
            # Setup mock response for remember extraction
            self.prov.responses.append({
                "content": '{"entities": [{"name": "Hamiltonian", "type": "Concept", "properties": {"description": "Total energy function"}}], "relationships": [{"source": "Hamiltonian", "target": "Lagrangian", "type": "legendre_transform", "properties": {}, "weight": 1.0}]}',
                "tool_calls": []
            })
            
            res = asyncio.run(kg.remember("Hamiltonian is related to Lagrangian via Legendre transform", agent))
            self.assertEqual(res["entities_extracted"], 1)
            self.assertEqual(res["relationships_extracted"], 1)
            
            # Recall
            recalled = kg.recall("Hamiltonian")
            self.assertEqual(recalled["primary_entity"], "Hamiltonian")
            self.assertTrue(any(n.name == "Hamiltonian" for n in recalled["nodes"]))
            
        finally:
            if os.path.exists(db_file):
                os.remove(db_file)

    def test_workflow_engine(self):
        from pitagora.agents.workflows import WorkflowEngine, WorkflowStep, WorkflowDefinition
        
        tutor = BaseAgent("tutor", "Tutor", self.prov, "Tutor prompt")
        researcher = BaseAgent("researcher", "Researcher", self.prov, "Researcher prompt")
        reviewer = BaseAgent("reviewer", "Reviewer", self.prov, "Reviewer prompt")
        explainer = BaseAgent("explainer", "Explainer", self.prov, "Explainer prompt")
        
        agents = {
            "tutor": tutor,
            "researcher": researcher,
            "reviewer": reviewer,
            "explainer": explainer
        }
        
        engine = WorkflowEngine(agents=agents)
        
        self.prov.responses.extend([
            {"content": "Research result content", "tool_calls": []},
            {"content": "Extracted concepts content", "tool_calls": []},
            {"content": "Verified feedback content", "tool_calls": []},
            {"content": "Final synthesized master report", "tool_calls": []}
        ])
        
        res = asyncio.run(engine.execute(
            inputs={"topic": "Quantum Gravity"},
            workflow_name_or_def="deep_research"
        ))
        
        self.assertEqual(res["workflow_name"], "deep_research")
        self.assertEqual(engine.workflow.merge_strategy, "last")
        self.assertIn("search", res["step_outputs"])
        self.assertEqual(res["step_outputs"]["search"], "Research result content")
        self.assertEqual(res["step_outputs"]["extract"], "Extracted concepts content")
        self.assertEqual(res["step_outputs"]["verify"], "Verified feedback content")
        self.assertEqual(res["final_output"], "Final synthesized master report")

    def test_debate_agent(self):
        from pitagora.agents.debate import DebateAgent
        prover = BaseAgent("prover", "Prover", self.prov, "Prover prompt")
        reviewer = BaseAgent("reviewer", "Reviewer", self.prov, "Reviewer prompt")
        debate_mgr = DebateAgent(self.prov)
        
        self.prov.responses.extend([
            {"content": "Prover Opening statement", "tool_calls": []},
            {"content": "Reviewer Opening statement", "tool_calls": []},
            {"content": "Reviewer critique", "tool_calls": []},
            {"content": "Prover response to critique", "tool_calls": []},
            {"content": "Prover critique of Reviewer", "tool_calls": []},
            {"content": "Reviewer response", "tool_calls": []},
            {"content": "Prover rebuttal", "tool_calls": []},
            {"content": "Reviewer rebuttal", "tool_calls": []},
            {"content": "Prover closing", "tool_calls": []},
            {"content": "Reviewer closing", "tool_calls": []},
            {
                "content": '{"verdict": "FOR", "confidence": 0.85, "strongest_arguments_pro": ["axiom A holds"], "strongest_arguments_con": ["edge case B exists"], "synthesis_summary": "Reconciliation summary."}',
                "tool_calls": []
            }
        ])
        
        res = asyncio.run(debate_mgr.run_debate(
            statement="P = NP",
            prover=prover,
            reviewer=reviewer
        ))
        
        self.assertEqual(res["verdict"], "FOR")
        self.assertEqual(res["confidence"], 0.85)
        self.assertIn("Prover Opening statement", res["transcript"][0]["content"])

    def test_reasoning_chain(self):
        from pitagora.agents.chain_of_thought import ReasoningChain
        prover = BaseAgent("prover", "Prover", self.prov, "Prover prompt")
        reviewer = BaseAgent("reviewer", "Reviewer", self.prov, "Reviewer prompt")
        
        chain = ReasoningChain(prover=prover, reviewer=reviewer, max_depth=3, max_branches=2, max_revisions=1)
        
        self.prov.responses.extend([
            {"content": "Thought 1", "tool_calls": []},
            {"content": "FAILED: error in definition", "tool_calls": []},
            {"content": "Thought 1 Revised", "tool_calls": []},
            {"content": "FAILED: still incorrect", "tool_calls": []},
            {"content": "Thought 2 alternative", "tool_calls": []},
            {"content": "VERIFIED: correct approach", "tool_calls": []},
            {"content": "Thought 3 QED", "tool_calls": []},
            {"content": "VERIFIED: correct", "tool_calls": []}
        ])
        
        res = asyncio.run(chain.solve("Prove theorem X"))
        
        self.assertTrue(res["success"])
        self.assertIn("Thought 2 alternative", res["solution"])
        self.assertIn("Thought 3 QED", res["solution"])
        
        tree_vis = res["tree_visualization"]
        self.assertIn("Step 1: Thought 1 Revised [FAILED]", tree_vis)
        self.assertIn("Step 2: Thought 2 alternative [VERIFIED]", tree_vis)
        self.assertIn("Step 2.1: Thought 3 QED [VERIFIED]", tree_vis)

if __name__ == "__main__":
    unittest.main()
