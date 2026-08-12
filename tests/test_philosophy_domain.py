"""Tests for the philosophy domain (TASK 4): concepts, workflow, skill YAML."""
import os

import pytest

from pitagora.concepts.graph import ConceptGraph


def _data_dir():
    # pitagora/data/ — packaged data
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "pitagora", "data",
    )


def test_philosophy_concepts_loaded_from_default_yaml():
    """Default packaged concepts.yaml must include the philosophy domain."""
    cg = ConceptGraph()  # loads default packaged concepts.yaml
    phil_ids = [cid for cid, d in cg.graph.items() if d.get("domain") == "philosophy"]
    expected = {
        "phil_formal_logic", "phil_propositional_logic", "phil_predicate_logic",
        "phil_modal_logic", "phil_epistemology", "phil_metaphysics",
        "phil_ethics", "phil_phil_math", "phil_phil_science", "phil_aesthetics",
    }
    assert expected.issubset(set(phil_ids))


def test_philosophy_prerequisites_chain():
    cg = ConceptGraph()
    # Formal Logic has no prerequisites
    assert cg.get_prerequisites("Formal Logic") == []
    # Propositional Logic needs Formal Logic
    prereqs = cg.get_prerequisites("Propositional Logic")
    assert "Formal Logic" in prereqs
    # Predicate Logic needs Propositional Logic
    prereqs = cg.get_prerequisites("Predicate Logic")
    assert "Propositional Logic" in prereqs
    # Modal Logic needs Predicate Logic
    assert "Predicate Logic" in cg.get_prerequisites("Modal Logic")


def test_philosophy_cross_domain_prerequisite():
    cg = ConceptGraph()
    # Philosophy of Mathematics needs epistemology AND calc_limits
    prereq_ids = cg.graph["phil_phil_math"]["prerequisites"]
    assert "phil_epistemology" in prereq_ids
    assert "calc_limits" in prereq_ids


def test_philosophy_learning_path():
    cg = ConceptGraph()
    path = cg.get_learning_path("Modal Logic")
    # Formal Logic must come before Propositional Logic before Predicate Logic
    assert path.index("Formal Logic") < path.index("Propositional Logic")
    assert path.index("Propositional Logic") < path.index("Predicate Logic")
    # Modal Logic itself appears at the end of its own learning path
    assert path[-1] == "Modal Logic"


def test_philosophical_reasoning_workflow_yaml_exists():
    path = os.path.join(_data_dir(), "workflows", "philosophical_reasoning.yaml")
    assert os.path.exists(path)
    try:
        import yaml
    except ImportError:
        pytest.skip("pyyaml not installed")
    with open(path) as f:
        data = yaml.safe_load(f)
    assert data["name"] == "philosophical_reasoning"
    step_ids = [s["id"] for s in data["steps"]]
    assert step_ids == ["clarify", "argue_for", "argue_against", "synthesize", "connect"]


def test_logic_skill_yaml_loads():
    path = os.path.join(
        os.path.dirname(_data_dir()), "skills", "builtin", "logic.yaml"
    )
    assert os.path.exists(path)
    try:
        import yaml
    except ImportError:
        pytest.skip("pyyaml not installed")
    with open(path) as f:
        data = yaml.safe_load(f)
    assert data["name"] == "Formal Logic"
    assert data["domain"] == "Philosophy"
    exercises = data["exercises"]
    levels = {e["level"] for e in exercises}
    assert {"beginner", "intermediate", "advanced"}.issubset(levels)
    # Three concept areas covered
    concepts = data["concepts"]
    assert any("truth table" in c.lower() for c in concepts)
    assert any("modus ponens" in c.lower() for c in concepts)
    assert any("quantifier" in c.lower() for c in concepts)
