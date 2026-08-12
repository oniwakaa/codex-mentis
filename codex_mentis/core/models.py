from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Message(BaseModel):
    role: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Conversation(BaseModel):
    topic: str
    messages: List[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

class Concept(BaseModel):
    id: str
    name: str
    domain: str
    prerequisites: List[str] = Field(default_factory=list)
    mastery_score: float = Field(default=0.0)
    last_reviewed: Optional[datetime] = None

class ProblemStatement(BaseModel):
    text: str
    domain: str
    difficulty: int

class Solution(BaseModel):
    steps: List[str] = Field(default_factory=list)
    verified: bool = Field(default=False)
    confidence: float = Field(default=0.0)

class MemoryEntry(BaseModel):
    id: Optional[int] = None
    layer: str = Field(..., description="L1 (Session), L2 (Topic), or L3 (Synthesis)")
    content: str
    embedding: Optional[List[float]] = None
    topic: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ReviewCard(BaseModel):
    concept: str
    ease_factor: float = Field(default=2.5)
    interval: int = Field(default=0)
    repetitions: int = Field(default=0)
    next_review: datetime
    last_reviewed: Optional[datetime] = None

class ConceptMastery(BaseModel):
    concept: str
    mastery_score: float = Field(default=0.0)
    attempts: int = Field(default=0)
    last_updated: datetime = Field(default_factory=datetime.now)

class SkillPerformance(BaseModel):
    skill_name: str
    success_rate: float = Field(default=0.0)
    avg_confidence: float = Field(default=0.0)
    use_count: int = Field(default=0)

class CurriculumPlan(BaseModel):
    target_concept: str
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

class Skill(BaseModel):
    name: str
    domain: str
    prompt_template: str
    success_rate: float = Field(default=0.0)
    use_count: int = Field(default=0)

class KBChunk(BaseModel):
    text: str
    embedding: Optional[List[float]] = None
    doc_path: str
    index: int

class KBDocument(BaseModel):
    path: str
    title: str
    subject: str
    chunks: List[KBChunk] = Field(default_factory=list)
