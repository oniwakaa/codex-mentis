import pytest
from datetime import datetime
from codex_mentis.core.models import (
    Message,
    Conversation,
    Concept,
    ProblemStatement,
    Solution,
    MemoryEntry,
    ReviewCard,
    ConceptMastery,
    SkillPerformance,
    CurriculumPlan,
    Skill,
    KBChunk,
    KBDocument
)

def test_message_model():
    msg = Message(role="user", content="hello", metadata={"debug": True})
    data = msg.model_dump()
    assert data["role"] == "user"
    assert Message.model_validate(data).content == "hello"

def test_conversation_model():
    messages = [Message(role="user", content="hello")]
    conv = Conversation(topic="greeting", messages=messages)
    data = conv.model_dump()
    assert data["topic"] == "greeting"
    assert len(data["messages"]) == 1

def test_concept_model():
    concept = Concept(id="c1", name="calculus", domain="math", prerequisites=["algebra"])
    data = concept.model_dump()
    assert data["id"] == "c1"
    assert data["prerequisites"] == ["algebra"]

def test_problem_statement_model():
    prob = ProblemStatement(text="solve equation", domain="algebra", difficulty=2)
    data = prob.model_dump()
    assert data["difficulty"] == 2

def test_solution_model():
    sol = Solution(steps=["step 1", "step 2"], verified=True, confidence=0.95)
    data = sol.model_dump()
    assert data["verified"] is True
    assert data["confidence"] == 0.95

def test_memory_entry_model():
    mem = MemoryEntry(layer="L2", content="Lagrangian mechanics summary", topic="physics")
    data = mem.model_dump()
    assert data["layer"] == "L2"
    assert isinstance(data["timestamp"], datetime)

def test_review_card_model():
    card = ReviewCard(concept="Calculus", next_review=datetime.now())
    data = card.model_dump()
    assert data["concept"] == "Calculus"

def test_concept_mastery_model():
    mastery = ConceptMastery(concept="Calculus", mastery_score=0.9, attempts=3)
    data = mastery.model_dump()
    assert data["mastery_score"] == 0.9

def test_skill_performance_model():
    perf = SkillPerformance(skill_name="algebra-solver", success_rate=0.8)
    data = perf.model_dump()
    assert data["success_rate"] == 0.8

def test_curriculum_plan_model():
    plan = CurriculumPlan(target_concept="quantum", steps=[{"step": 1, "concept": "calculus"}])
    data = plan.model_dump()
    assert data["target_concept"] == "quantum"
    assert len(data["steps"]) == 1

def test_skill_model():
    skill = Skill(name="solve", domain="math", prompt_template="Solve: {problem}")
    data = skill.model_dump()
    assert data["name"] == "solve"

def test_kb_chunk_and_document_models():
    chunk = KBChunk(text="chunk 1", doc_path="doc.md", index=0)
    doc = KBDocument(path="doc.md", title="Document", subject="physics", chunks=[chunk])
    
    doc_data = doc.model_dump()
    assert doc_data["title"] == "Document"
    assert len(doc_data["chunks"]) == 1
    assert doc_data["chunks"][0]["text"] == "chunk 1"
