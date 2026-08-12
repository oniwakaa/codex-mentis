from typing import Optional, Dict, Any
from codex_mentis.agents.base import BaseAgent, AgentResponse
from codex_mentis.agents.providers.base import BaseProvider

TUTOR_SYSTEM_PROMPT = """You are the Tutor Agent for Codex Mentis. Your role is to guide students through complex mathematics and physics using a Socratic teaching style.

Guidelines:
1. Socratic Method: Do not give direct answers immediately. Instead, ask guiding questions to help the student think and deduce the answers themselves.
2. Adaptability: Adapt your explanation depth, vocabulary, and pacing to the student's requested level.
3. Intuition & Analogies: Use physical intuition and everyday analogies to explain abstract mathematical or physical models before diving into formal proofs.
4. Format: Use LaTeX for mathematical notation (e.g., $E = mc^2$ or $$i\\hbar\\frac{\\partial}{\\partial t}\\Psi = \\hat{H}\\Psi$$). Keep markdown formatting clean and professional.
"""

class TutorAgent(BaseAgent):
    def __init__(self, provider: BaseProvider):
        super().__init__(
            name="Tutor",
            role="Socratic Mathematics and Physics Instructor",
            provider=provider,
            system_prompt=TUTOR_SYSTEM_PROMPT
        )

    def explain_concept(self, topic: str, level: str = "beginner") -> AgentResponse:
        """
        Explain a math/physics concept targeted at a specific understanding level.
        """
        prompt = (
            f"Explain the following topic: '{topic}'.\n"
            f"Target student level: {level}.\n"
            f"Provide a Socratic introduction, clear explanations with analogies, and end with a guiding question."
        )
        return self.think(prompt)

    def socratic_question(self, topic: str, student_response: str) -> AgentResponse:
        """
        Respond to a student's answer/reasoning about a topic with a guiding question.
        """
        prompt = (
            f"We are discussing: '{topic}'.\n"
            f"The student responded with: \"{student_response}\".\n"
            f"Acknowledge what is correct or interesting, identify any misconceptions without showing the answer, "
            f"and ask a Socratic guiding question to help them correct or refine their thinking."
        )
        return self.think(prompt)

    def generate_exercise(self, concept: str, difficulty: str = "medium") -> AgentResponse:
        """
        Generate a practice problem for a concept.
        """
        prompt = (
            f"Generate an exercise or practice problem on the concept: '{concept}'.\n"
            f"Difficulty: {difficulty}.\n"
            f"Make it clear, challenging, and conceptual. Do not provide the solution directly, "
            f"but you can embed hints or guidance on how to start."
        )
        return self.think(prompt)

    def check_answer(self, exercise: str, answer: str) -> AgentResponse:
        """
        Evaluate a student's answer to an exercise and guide them if incorrect.
        """
        prompt = (
            f"Check the student's answer to the following exercise:\n"
            f"Exercise:\n{exercise}\n\n"
            f"Student's Answer:\n{answer}\n\n"
            f"Evaluate the correctness. If correct, praise the student and explain why they are right. "
            f"If incorrect, point out where the reasoning went wrong and ask a guiding question to prompt correction."
        )
        return self.think(prompt)
