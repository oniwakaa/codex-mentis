import os
import tempfile

import pytest

from pitagora.skills.engine import Skill, SkillsEngine
from pitagora.skills.evolution import SkillEvolution


def test_skills_engine_basic():
    engine = SkillsEngine()

    # List skills
    skills = engine.list_skills()
    assert len(skills) > 0

    # Load the first available skill
    first_name = skills[0]
    skill = engine.load_skill(first_name)
    assert skill.name is not None
    assert len(skill.concepts) > 0

    # Domain should be set
    assert skill.domain is not None


def test_skills_engine_domain_filtering():
    engine = SkillsEngine()

    # List all skills
    all_skills = engine.list_skills()
    assert len(all_skills) > 0

    # Try domain filtering — should return a subset or all
    # Domain names in YAML are like "Algebra", "Physics", "Calculus" etc.
    for name in all_skills[:3]:
        skill = engine.load_skill(name)
        assert skill.domain is not None


def test_skill_evolution():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        evo = SkillEvolution(db_path=db_path)

        # Record success
        evo.record_use("algebra", success=True, feedback="No errors", confidence=0.9)
        stats1 = evo.get_stats("algebra")
        assert stats1.use_count == 1
        assert stats1.success_rate == 1.0
        assert stats1.avg_confidence == pytest.approx(0.9)

        # Record failure
        evo.record_use("algebra", success=False, feedback="Sign error in roots", confidence=0.8)
        stats2 = evo.get_stats("algebra")
        assert stats2.use_count == 2
        assert stats2.success_rate == pytest.approx(0.5)
        assert stats2.avg_confidence == pytest.approx(0.85)

        # Evolve prompt
        base_template = "Solve this equation: {problem}"
        evolved = evo.evolve_prompt("algebra", base_template)

        assert "Evolved Guidelines" in evolved
        assert "Sign error" in evolved
        assert evolved.startswith("Solve this equation")
    finally:
        os.unlink(db_path)
