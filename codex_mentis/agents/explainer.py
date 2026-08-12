import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from codex_mentis.agents.base import BaseAgent, AgentResponse
from codex_mentis.agents.providers.base import BaseProvider

logger = logging.getLogger(__name__)

EXPLAINER_SYSTEM_PROMPT = """You are the Explainer Agent for Codex Mentis. Your goal is to democratize complex mathematical and physical concepts using advanced pedagogical techniques.

You specialize in:
1. The Feynman Technique: Explain concepts simply, identify gaps in understanding, return to the source material to refine, and simplify further with analogies.
2. Five Levels of Understanding: Break down any topic into five custom levels:
   - Level 1: Child (ELIF5, using concrete toys/animals, no math)
   - Level 2: Beginner (High school, intuitive algebra, basic geometry)
   - Level 3: Intermediate (College student, calculus, standard representations)
   - Level 4: Advanced (Graduate student, formal notation, proofs, derivations)
   - Level 5: Expert (Researcher, academic nuance, open questions, edge cases)
3. Intuition Maps: Map formal mathematical equations or physical laws to their core physical behaviors, visual representations, and qualitative behaviors.
4. Side-by-side Mode: Present a dual format where the technical/mathematical rigor is placed alongside a plain English intuitive translation.

Use clean Markdown formatting. When in side-by-side mode, you can use markdown tables or side-by-side columns if requested, or present them as alternating block sections clearly labeled.
"""

class DifficultyAssessment(BaseModel):
    concept: str = Field(description="The concept being assessed")
    estimated_difficulty: str = Field(description="Rating from: trivial, easy, moderate, challenging, extreme")
    prerequisites: List[str] = Field(description="Prerequisite topics needed to grasp this concept")
    key_cognitive_obstacles: List[str] = Field(description="List of common misconceptions or mental blocks")

class Analogy(BaseModel):
    concept: str = Field(description="The concept to describe")
    analogy_name: str = Field(description="Catchy name for the analogy")
    scenario: str = Field(description="The real-world scenario or metaphor used")
    mapping: Dict[str, str] = Field(description="Map concept elements to analogy elements")
    limitations: List[str] = Field(description="Where the analogy breaks down or doesn't match the math/physics")

class DecomposedConcept(BaseModel):
    concept: str = Field(description="The main topic")
    sub_concepts: List[str] = Field(description="Ordered list of sub-components or building blocks")
    milestones: List[str] = Field(description="Checkpoints indicating progress toward mastery")

class ExplainerAgent(BaseAgent):
    def __init__(self, provider: BaseProvider, concept_graph: Optional[Any] = None):
        super().__init__(
            name="Explainer",
            role="Feynman Pedagogy & Concept Simplifier",
            provider=provider,
            system_prompt=EXPLAINER_SYSTEM_PROMPT
        )
        self.concept_graph = concept_graph

        # Register difficulty_assessor
        self.register_tool(
            "difficulty_assessor",
            {
                "name": "difficulty_assessor",
                "description": "Assess the difficulty of a concept and retrieve its prerequisites and cognitive hurdles.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept": {
                            "type": "string",
                            "description": "The mathematical or physical concept to assess."
                        }
                    },
                    "required": ["concept"]
                }
            },
            self.tool_difficulty_assessor
        )

        # Register analogy_generator
        self.register_tool(
            "analogy_generator",
            {
                "name": "analogy_generator",
                "description": "Generate a creative, robust everyday analogy for an abstract topic.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept": {
                            "type": "string",
                            "description": "The abstract concept needing an analogy."
                        },
                        "domain": {
                            "type": "string",
                            "description": "The source domain of the analogy (e.g., cooking, traffic, oceans, sports).",
                            "default": "everyday life"
                        }
                    },
                    "required": ["concept"]
                }
            },
            self.tool_analogy_generator
        )

        # Register concept_decomposer
        self.register_tool(
            "concept_decomposer",
            {
                "name": "concept_decomposer",
                "description": "Decompose a complex concept into its ordered constituent sub-concepts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept": {
                            "type": "string",
                            "description": "The target concept to break down."
                        }
                    },
                    "required": ["concept"]
                }
            },
            self.tool_concept_decomposer
        )

    async def tool_difficulty_assessor(self, concept: str) -> str:
        """
        Assess difficulty of a concept. Returns a structured JSON assessment.
        """
        # If we have concept graph, check if it contains the concept
        prereqs = []
        if self.concept_graph:
            try:
                prereqs = self.concept_graph.get_prerequisites(concept) or []
            except Exception:
                pass

        # Call LLM for dynamic assessment
        prompt = f"Perform a difficulty assessment for the concept: '{concept}'."
        if prereqs:
            prompt += f" Known structural prerequisites from curriculum graph: {prereqs}"
            
        try:
            assessment = await self.athink_structured(prompt, DifficultyAssessment)
            return assessment.model_dump_json(indent=2)
        except Exception as e:
            logger.error(f"Error in tool_difficulty_assessor: {e}")
            # Fallback
            fallback = DifficultyAssessment(
                concept=concept,
                estimated_difficulty="moderate",
                prerequisites=prereqs or [f"Basic {concept} fundamentals"],
                key_cognitive_obstacles=["Abstraction level", "Mathematical notation"]
            )
            return fallback.model_dump_json(indent=2)

    async def tool_analogy_generator(self, concept: str, domain: str = "everyday life") -> str:
        """
        Generate analogy for a concept.
        """
        prompt = f"Generate an analogy for: '{concept}' using the source domain: '{domain}'."
        try:
            analogy = await self.athink_structured(prompt, Analogy)
            return analogy.model_dump_json(indent=2)
        except Exception as e:
            logger.error(f"Error in tool_analogy_generator: {e}")
            fallback = Analogy(
                concept=concept,
                analogy_name=f"The {concept} Metaphor",
                scenario=f"A workflow representing how {concept} functions.",
                mapping={"source": "target"},
                limitations=["Oversimplification"]
            )
            return fallback.model_dump_json(indent=2)

    async def tool_concept_decomposer(self, concept: str) -> str:
        """
        Decompose concept into subcomponents.
        """
        prompt = f"Decompose the following concept into its sub-concepts and learning milestones: '{concept}'."
        try:
            decomposition = await self.athink_structured(prompt, DecomposedConcept)
            return decomposition.model_dump_json(indent=2)
        except Exception as e:
            logger.error(f"Error in tool_concept_decomposer: {e}")
            fallback = DecomposedConcept(
                concept=concept,
                sub_concepts=[f"Introduction to {concept}", f"Core mechanics of {concept}", f"Advanced {concept}"],
                milestones=[f"Understand {concept} basic definition", f"Apply {concept} to problems"]
            )
            return fallback.model_dump_json(indent=2)

    async def explain_level(self, topic: str, level: str) -> AgentResponse:
        """
        Explain a topic at a specific level of understanding (Child, Beginner, Intermediate, Advanced, Expert).
        """
        prompt = (
            f"Explain the following topic: '{topic}'\n"
            f"Target Level: {level}\n\n"
            f"Please tailor your explanation's vocabulary, mathematics, and tone precisely to the target level."
        )
        return await self.athink(prompt)

    async def feynman_explanation(self, topic: str) -> AgentResponse:
        """
        Explain using the Feynman Technique.
        """
        prompt = (
            f"Explain the topic '{topic}' using the Feynman Technique.\n\n"
            f"Structure your response to:\n"
            f"1. Explain it so simply that a 10-year-old would understand the core idea.\n"
            f"2. Identify the critical 'gaps' or points of friction where understanding usually breaks down.\n"
            f"3. Return to the source details: provide a precise, simple explanation of those tricky parts.\n"
            f"4. Wrap up with a highly intuitive, memorable analogy."
        )
        return await self.athink(prompt)

    async def generate_intuition_map(self, topic: str) -> AgentResponse:
        """
        Generate an intuition map for the topic.
        """
        prompt = (
            f"Generate an Intuition Map for '{topic}'.\n\n"
            f"Include:\n"
            f"- Core Equation or Statement\n"
            f"- Intuitive Translation (What it really means physically)\n"
            f"- Sensory/Visual Representation (How to visualize it or feel it)\n"
            f"- Qualititative Behavior (If parameter X increases, what happens to Y?)"
        )
        return await self.athink(prompt)

    async def side_by_side_explanation(self, topic: str) -> AgentResponse:
        """
        Create a side-by-side technical vs. plain English comparison.
        """
        prompt = (
            f"Generate a side-by-side explanation for '{topic}'.\n\n"
            f"Format this as a Markdown table with two columns:\n"
            f"1. **Technical Rigor** (Formal math/physics definitions, equations, exact conditions)\n"
            f"2. **Intuitive Translation** (Plain English analogies, everyday comparisons, what the math is saying in common language)"
        )
        return await self.athink(prompt)
