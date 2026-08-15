import os

import pytest

from pitagora.agents import BaseAgent
from pitagora.memory.knowledge_graph import EntityNode, KnowledgeGraph, Relationship
from tests.conftest import MockProvider


def test_knowledge_graph(temp_db):
    db_file = temp_db + "_kg.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    kg = KnowledgeGraph(db_path=db_file)

    try:
        # 1. Add entity
        e1_id = kg.add_entity("Lagrangian Mechanics", "Concept", {"difficulty": "challenging"})
        e2_id = kg.add_entity("Action Principle", "Concept", {"difficulty": "moderate"})

        assert e1_id == "lagrangian_mechanics"
        assert e2_id == "action_principle"

        # 2. Find entity
        e1 = kg.find_entity("Lagrangian Mechanics")
        assert e1 is not None
        assert e1.name == "Lagrangian Mechanics"
        assert e1.properties["difficulty"] == "challenging"

        # 3. Add relationship
        kg.add_relationship(
            "Action Principle", "Lagrangian Mechanics", "prerequisite_of", {"weight": 1.0}
        )

        # 4. Find related
        related = kg.find_related("Action Principle", depth=1)
        assert len(related) == 1
        assert related[0][0].name == "Lagrangian Mechanics"
        assert related[0][1].rel_type == "prerequisite_of"

        # 5. Semantic Search
        matches = kg.semantic_search("Lagrangian", limit=1)
        assert len(matches) == 1
        assert matches[0].id == "lagrangian_mechanics"

        # 6. Graph traversal
        subgraph = kg.graph_traversal("Action Principle", max_depth=1)
        assert len(subgraph["nodes"]) == 2
        assert len(subgraph["relationships"]) == 1

        # 7. Merge entities
        e3_id = kg.add_entity("Lagrange Formalism", "Concept", {"alternate": "yes"})
        kg.add_relationship("Lagrange Formalism", "Action Principle", "related_to")
        merged_id = kg.merge_entities("lagrangian_mechanics", "lagrange_formalism")
        assert merged_id == "lagrangian_mechanics"

        # The merged relationship should now point to lagrangian_mechanics
        related_merged = kg.find_related("Action Principle", depth=1)
        assert len(related_merged) == 2

        # 8. Context window
        context_str = kg.get_context_window("lagrangian_mechanics")
        assert "Lagrangian Mechanics" in context_str

        # 9. Temporal Query
        temporal = kg.temporal_query("lagrangian_mechanics")
        assert len(temporal) > 0

        # 10. Improve weight
        kg.improve("lagrangian_mechanics", "positive test feedback", 0.5)
        traversed = kg.find_related("lagrangian_mechanics", depth=1)
        assert any(r[1].weight > 1.0 for r in traversed)

        # 11. Forget
        kg.forget("action_principle")
        assert kg.find_entity("action_principle") is None

    finally:
        if os.path.exists(db_file):
            os.remove(db_file)


@pytest.mark.asyncio
async def test_knowledge_graph_remember_recall(temp_db, mock_provider):
    db_file = temp_db + "_kg_rr.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    kg = KnowledgeGraph(db_path=db_file)

    try:
        agent = BaseAgent("TestAgent", "Tester", mock_provider, "Mock prompt")

        # Setup mock response for remember extraction
        mock_provider.responses.append(
            {
                "content": '{"entities": [{"name": "Hamiltonian", "type": "Concept", "properties": {"description": "Total energy function"}}], "relationships": [{"source": "Hamiltonian", "target": "Lagrangian", "type": "legendre_transform", "properties": {}, "weight": 1.0}]}',
                "tool_calls": [],
            }
        )

        res = await kg.remember(
            "Hamiltonian is related to Lagrangian via Legendre transform", agent
        )
        assert res["entities_extracted"] == 1
        assert res["relationships_extracted"] == 1

        # Recall
        recalled = kg.recall("Hamiltonian")
        assert recalled["primary_entity"] == "Hamiltonian"
        assert any(n.name == "Hamiltonian" for n in recalled["nodes"])

    finally:
        if os.path.exists(db_file):
            os.remove(db_file)
