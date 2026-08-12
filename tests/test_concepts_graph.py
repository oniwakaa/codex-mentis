import pytest
import os
from codex_mentis.concepts.graph import ConceptGraph

def test_concept_graph_load_seed(temp_yaml):
    # Using temp_yaml will load the custom structure written by fixture
    cg = ConceptGraph(yaml_path=temp_yaml)
    assert "Calculus" in cg.graph
    assert "Quantum Mechanics" in cg.graph
    
    # Check sync_bidirectional
    assert "Quantum Mechanics" in cg.graph["Classical Mechanics"]["dependents"]

def test_concept_graph_prerequisites_and_dependents(temp_yaml):
    cg = ConceptGraph(yaml_path=temp_yaml)
    
    prereqs = cg.get_prerequisites("Quantum Mechanics")
    assert "Classical Mechanics" in prereqs
    assert "Calculus" in prereqs
    
    dependents = cg.get_dependents("Calculus")
    assert "Classical Mechanics" in dependents
    assert "Quantum Mechanics" in dependents

def test_concept_graph_learning_path(temp_yaml):
    cg = ConceptGraph(yaml_path=temp_yaml)
    path = cg.get_learning_path("Quantum Mechanics")
    
    # Must be topologically sorted: Calculus must precede Classical Mechanics, etc.
    assert path.index("Calculus") < path.index("Classical Mechanics")
    assert path.index("Classical Mechanics") < path.index("Quantum Mechanics")

def test_concept_graph_optimized_path(temp_yaml):
    cg = ConceptGraph(yaml_path=temp_yaml)
    
    # Check optimized path with some mastered concepts
    path = cg.get_optimized_path("Quantum Mechanics", mastered_concepts=["Calculus", "Linear Algebra"])
    assert "Calculus" not in path
    assert "Linear Algebra" not in path
    assert path == ["Classical Mechanics", "Quantum Mechanics"]

def test_concept_graph_add_concept(temp_yaml):
    cg = ConceptGraph(yaml_path=temp_yaml)
    cg.add_concept("Quantum Computing", ["Quantum Mechanics"], "Introduction to qubits", "Physics", 5, 120)
    
    assert "Quantum Computing" in cg.graph
    assert "Quantum Computing" in cg.get_dependents("Quantum Mechanics")

def test_concept_graph_search_and_cluster(temp_yaml):
    cg = ConceptGraph(yaml_path=temp_yaml)
    
    # Cluster
    clusters = cg.get_clusters_by_domain()
    # By default, domain is 'General' if not specified in temp_yaml
    assert "General" in clusters
    
    # Search
    results = cg.search_concepts("Quantum")
    assert len(results) > 0
    assert results[0][0] == "Quantum Mechanics"

def test_concept_graph_exports(temp_yaml, tmp_path):
    cg = ConceptGraph(yaml_path=temp_yaml)
    
    json_dest = str(tmp_path / "graph.json")
    dot_dest = str(tmp_path / "graph.dot")
    
    cg.export_to_json(json_dest)
    cg.export_to_dot(dot_dest)
    
    assert os.path.exists(json_dest)
    assert os.path.exists(dot_dest)

def test_concept_graph_visualize(temp_yaml):
    cg = ConceptGraph(yaml_path=temp_yaml)
    ascii_tree = cg.visualize("Quantum Mechanics")
    assert "Quantum Mechanics" in ascii_tree
    assert "Calculus" in ascii_tree
