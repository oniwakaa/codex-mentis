import pytest
import os
from codex_mentis.skills.engine import SkillsEngine, Skill
from codex_mentis.skills.evolution import SkillEvolution

def test_skills_engine_basic():
    engine = SkillsEngine()
    
    # List skills
    skills = engine.list_skills()
    assert len(skills) > 0
    assert "algebra" in skills
    assert "calculus" in skills
    
    # Load skill
    algebra = engine.load_skill("algebra")
    assert algebra.name == "Algebra Solving" or "Algebra" in algebra.name
    assert "algebra" in algebra.concepts
    
    # Render prompt
    ctx = {"problem": "Solve x + 2 = 5"}
    prompt = engine.get_prompt(algebra, ctx)
    assert "Solve x + 2 = 5" in prompt
    assert algebra.domain in prompt

def test_skills_engine_domain_filtering():
    engine = SkillsEngine()
    
    math_skills = engine.list_skills(domain="Mathematics")
    physics_skills = engine.list_skills(domain="Physics")
    
    assert "algebra" in math_skills or "calculus" in math_skills
    # mechanics is physics
    assert "mechanics" in physics_skills or "electromagnetism" in physics_skills

def test_skill_evolution(temp_db):
    evo = SkillEvolution(db_path=temp_db)
    
    # Record success
    evo.record_use("algebra", success=True, feedback="No errors", confidence=0.9)
    stats1 = evo.get_stats("algebra")
    assert stats1.use_count == 1
    assert stats1.success_rate == 1.0
    assert stats1.avg_confidence == 0.9
    
    # Record failure
    evo.record_use("algebra", success=False, feedback="Sign error in roots", confidence=0.8)
    stats2 = evo.get_stats("algebra")
    assert stats2.use_count == 2
    assert stats2.success_rate == 0.5
    assert stats2.avg_confidence == 0.85
    
    # Evolve prompt
    base_template = "Solve this equation: {problem}"
    evolved = evo.evolve_prompt("algebra", base_template)
    
    assert "Evolved Guidelines" in evolved
    assert "Sign error in roots" in evolved
    assert evolved.startswith("Solve this equation")
