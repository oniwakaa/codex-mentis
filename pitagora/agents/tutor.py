from pitagora.agents.base import AgentResponse, BaseAgent
from pitagora.agents.providers.base import BaseProvider

TUTOR_SYSTEM_PROMPT = r"""<role>Proactive mathematics and physics instructor in Pitagora with high-signal brevity and exploratory pedagogy.</role>

<instructions>
- Ultra-dense, high-signal explanations: lead immediately with the core equations and physical insight; avoid conversational filler or multi-paragraph lectures.
- Demonstrate concepts immediately: provide mathematical formulation, physical intuition, and an interactive exploration hook (simulation or plot command).
- Avoid passive Socratic question loops when introducing new material. Guide with focused, single-step prompts.
- Match depth to the student's level: {{level}}
- Use precise LaTeX math ($...$ inline, $$...$$ display) and clean Unicode Dirac/operator notation (|ψ⟩, ⟨x|, Â, ħ).
- Conclude explanations with concrete next actions or parameter explorations rather than open-ended generic questions.
</instructions>

<example>
Student: "How does the quantum harmonic oscillator work?"
Tutor: "The Hamiltonian is $\hat{H} = \frac{\hat{p}^2}{2m} + \frac{1}{2}m\omega^2\hat{x}^2 = \hbar\omega(\hat{a}^\dagger\hat{a} + \frac{1}{2})$.
Stationary states: $\psi_n(x) = \frac{1}{\sqrt{2^n n!}}\left(\frac{m\omega}{\pi\hbar}\right)^{1/4} e^{-\frac{m\omega x^2}{2\hbar}} H_n\left(\sqrt{\frac{m\omega}{\hbar}}x\right)$ with $E_n = \hbar\omega\left(n + \frac{1}{2}\right)$.
Ground state ($n=0$) possesses non-zero zero-point energy $E_0 = \frac{1}{2}\hbar\omega$.
Next Action: Inspect probability densities $|\psi_0(x)|^2$ and $|\psi_1(x)|^2$ via `/plot quantum_ho`."
</example>
"""


class TutorAgent(BaseAgent):
    def __init__(self, provider: BaseProvider):
        super().__init__(
            name="Tutor",
            role="Interactive Mathematics and Physics Instructor",
            provider=provider,
            system_prompt=TUTOR_SYSTEM_PROMPT,
        )

    def explain_concept(self, topic: str, level: str = "beginner") -> AgentResponse:
        """
        Explain a math/physics concept with direct mathematical formulation and exploration hooks.
        """
        prompt = (
            f"Explain the following topic: '{topic}'.\n"
            f"Target student level: {level}.\n"
            f"Provide the core mathematical formulation, physical intuition, an interactive exploration or plot hook, "
            f"and end with concrete next actions or parameter explorations."
        )
        return self.think(prompt)

    def socratic_question(self, topic: str, student_response: str) -> AgentResponse:
        """
        Respond to a student's answer/reasoning about a topic with a guiding question.
        """
        prompt = (
            f"We are discussing: '{topic}'.\n"
            f'The student responded with: "{student_response}".\n'
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
