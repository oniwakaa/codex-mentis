"""Tests for Philosophical Dilemmas & Thought Experiments engine."""

from pitagora.knowledge.dilemma import DilemmaEngine, BUILTIN_DILEMMAS


def test_dilemma_scenarios_loaded():
    engine = DilemmaEngine()
    scenarios = engine.list_scenarios()
    assert len(scenarios) >= 5
    assert any(s["id"] == "ship_of_theseus" for s in scenarios)
    assert any(s["id"] == "maxwells_demon" for s in scenarios)
    assert any(s["id"] == "chinese_room" for s in scenarios)


def test_record_choice_and_probing():
    engine = DilemmaEngine()
    result = engine.record_choice("ship_of_theseus", "A")
    assert "error" not in result
    assert "Functional Continuity" in result["stance"]
    assert len(result["counter_probe"]) > 10
    assert len(result["traditions"]) > 0

    # Record second choice
    res2 = engine.record_choice("trolley_fatman", "A")
    assert "error" not in res2
    assert "Utilitarianism" in res2["stance"]


def test_epistemic_profile_consistency():
    engine = DilemmaEngine()
    engine.record_choice("trolley_fatman", "A")  # Utilitarian
    engine.record_choice("ship_of_theseus", "B")  # Essentialist

    profile = engine.compute_epistemic_profile()
    assert profile["completed_scenarios"] == 2
    assert "ship_of_theseus" in profile["stances_registered"]
    assert "trolley_fatman" in profile["stances_registered"]
    assert "summary" in profile
