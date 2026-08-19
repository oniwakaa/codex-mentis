"""Feynman Reverse-Teaching Engine (Teach-Back Sandbox).

In this mode, the learner assumes the role of the teacher (Feynman technique)
and explains a target concept in Mathematics, Physics, or Philosophy to Pitagora.
Pitagora plays the role of a curious, thoughtful novice student who asks
inquisitive clarifying questions, detects ungrounded jargon, checks logical/mathematical
rigor, identifies conceptual gaps, and logs misconceptions directly into the learner profile.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from pitagora.memory.store import MemoryStore
from pitagora.memory.spaced_repetition import SpacedRepetition

logger = logging.getLogger(__name__)


@dataclass
class FeynmanRubric:
    clarity: float = 0.0  # 0.0 - 1.0 (plain language, jargon grounded)
    precision: float = 0.0  # 0.0 - 1.0 (factual/mathematical correctness)
    analogy: float = 0.0  # 0.0 - 1.0 (effective concrete intuition)
    depth: float = 0.0  # 0.0 - 1.0 (causal/first-principles reasoning)

    @property
    def overall(self) -> float:
        return (
            0.30 * self.clarity
            + 0.30 * self.precision
            + 0.20 * self.analogy
            + 0.20 * self.depth
        )


@dataclass
class FeynmanEvaluation:
    rubric: FeynmanRubric = field(default_factory=FeynmanRubric)
    jargon_used: list[str] = field(default_factory=list)
    misconceptions: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    student_question: str = ""
    is_mastered: bool = False
    feedback_summary: str = ""


FEYNMAN_STUDENT_PROMPT = """You are a bright, curious student being taught a concept by your teacher (the user).
Concept being taught: "{concept}"
Domain: "{domain}"

Your goal is to evaluate the teacher explanation using the Feynman Technique:
1. Did they explain it in simple, intuitive terms without hiding behind jargon?
2. Is the explanation mathematically, physically, or philosophically sound?
3. Did they use an effective analogy or concrete example?
4. Are there logical leaps, circular definitions, or unaddressed edge cases?

Analyze the teacher explanation and respond ONLY with a valid JSON object matching this schema:
{{
  "clarity": <float 0.0 to 1.0>,
  "precision": <float 0.0 to 1.0>,
  "analogy": <float 0.0 to 1.0>,
  "depth": <float 0.0 to 1.0>,
  "jargon_used": [<list of complex terms used without plain-language explanation>],
  "misconceptions": [<list of incorrect assumptions or conceptual errors, if any>],
  "strengths": [<list of strong intuitive points or good analogies>],
  "student_question": "<Inquisitive follow-up question as a student testing a specific edge case or asking for intuition on a step>",
  "is_mastered": <true if the explanation is crystal clear and complete, false otherwise>,
  "feedback_summary": "<One concise sentence summarizing the explanation quality>"
}}
Do NOT output markdown fences. Output raw JSON only.
"""


class FeynmanSession:
    """Manages an interactive reverse-teaching Feynman dialogue."""

    def __init__(
        self,
        concept: str,
        domain: str = "STEM/Philosophy",
        chat_completion_fn: Callable[..., str] | None = None,
        memory_store: MemoryStore | None = None,
        spaced_repetition: SpacedRepetition | None = None,
    ):
        self.concept = concept
        self.domain = domain
        self._chat = chat_completion_fn
        self.memory = memory_store or MemoryStore()
        self.sr = spaced_repetition or SpacedRepetition()
        self.history: list[dict[str, Any]] = []
        self.evaluations: list[FeynmanEvaluation] = []

    def evaluate_explanation(
        self,
        explanation: str,
        config: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> FeynmanEvaluation:
        """Evaluates an explanation turn from the learner."""
        user_msg = f"Teacher explanation:\n\n{explanation}"

        if not self._chat:
            evaluation = self._heuristic_evaluation(explanation)
        else:
            system_msg = FEYNMAN_STUDENT_PROMPT.format(
                concept=self.concept, domain=self.domain
            )
            messages = [
                {"role": "system", "content": system_msg},
                *self.history,
                {"role": "user", "content": user_msg},
            ]

            try:
                raw_response = self._chat(messages, model=model, config=config)
                evaluation = self._parse_evaluation(raw_response)
            except Exception as e:
                logger.warning("Feynman evaluation LLM call failed: %s", e)
                evaluation = self._heuristic_evaluation(explanation)

        self.evaluations.append(evaluation)
        self.history.append({"role": "user", "content": user_msg})
        self.history.append(
            {"role": "assistant", "content": evaluation.student_question}
        )

        for misc in evaluation.misconceptions:
            self.memory.record_misconception(
                topic=self.domain,
                concept=self.concept,
                misconception=misc,
                resolution=f"Clarified during Feynman teach-back session on {self.concept}",
            )
            self.sr.schedule_review(f"{self.concept}: {misc}", quality=1)

        return evaluation

    def _heuristic_evaluation(self, explanation: str) -> FeynmanEvaluation:
        """Deterministic evaluation fallback."""
        words = explanation.split()
        word_count = len(words)
        has_analogy = any(
            w in explanation.lower()
            for w in ["like", "imagine", "analogous", "for example", "picture", "consider"]
        )
        has_equations = any(c in explanation for c in ["=", "+", "-", "*", "/", "^", "\\"])

        clarity = min(1.0, max(0.4, word_count / 50.0))
        precision = 0.8 if has_equations or word_count > 30 else 0.5
        analogy = 0.9 if has_analogy else 0.3
        depth = 0.7 if word_count > 40 else 0.4

        rubric = FeynmanRubric(
            clarity=clarity, precision=precision, analogy=analogy, depth=depth
        )
        jargon = [
            w for w in ["eigenvalue", "entropy", "epistemic", "tensor", "isomorphism", "mereology"]
            if w in explanation.lower()
        ]

        return FeynmanEvaluation(
            rubric=rubric,
            jargon_used=jargon,
            misconceptions=[],
            strengths=["Clear plain-language phrasing" if clarity > 0.6 else "Good start"],
            student_question=f"Could you explain how {self.concept} applies in a concrete physical or everyday situation?",
            is_mastered=rubric.overall >= 0.85,
            feedback_summary="Good explanation with clear progression.",
        )

    def _parse_evaluation(self, raw: str) -> FeynmanEvaluation:
        """Parses the LLM JSON evaluation response."""
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("\n", 1)[-1] if "\n" in s else s
            if s.endswith("```"):
                s = s[:-3].strip()

        try:
            data = json.loads(s)
            rubric = FeynmanRubric(
                clarity=float(data.get("clarity", 0.5)),
                precision=float(data.get("precision", 0.5)),
                analogy=float(data.get("analogy", 0.5)),
                depth=float(data.get("depth", 0.5)),
            )
            return FeynmanEvaluation(
                rubric=rubric,
                jargon_used=list(data.get("jargon_used", [])),
                misconceptions=list(data.get("misconceptions", [])),
                strengths=list(data.get("strengths", [])),
                student_question=str(
                    data.get("student_question", "Can you unpack that further?")
                ),
                is_mastered=bool(data.get("is_mastered", False)),
                feedback_summary=str(data.get("feedback_summary", "")),
            )
        except Exception:
            return self._heuristic_evaluation(raw)

    def generate_final_report(self) -> dict[str, Any]:
        """Synthesizes all turns into a final Feynman Teach-Back Report."""
        if not self.evaluations:
            return {
                "concept": self.concept,
                "overall_score": 0.0,
                "turns_completed": 0,
                "mastered": False,
                "rubric": FeynmanRubric(),
                "all_misconceptions": [],
                "all_jargon": [],
            }

        avg_clarity = sum(e.rubric.clarity for e in self.evaluations) / len(self.evaluations)
        avg_precision = sum(e.rubric.precision for e in self.evaluations) / len(self.evaluations)
        avg_analogy = sum(e.rubric.analogy for e in self.evaluations) / len(self.evaluations)
        avg_depth = sum(e.rubric.depth for e in self.evaluations) / len(self.evaluations)

        final_rubric = FeynmanRubric(
            clarity=avg_clarity,
            precision=avg_precision,
            analogy=avg_analogy,
            depth=avg_depth,
        )

        all_misconceptions = []
        all_jargon = []
        for e in self.evaluations:
            all_misconceptions.extend(e.misconceptions)
            all_jargon.extend(e.jargon_used)

        return {
            "concept": self.concept,
            "domain": self.domain,
            "overall_score": final_rubric.overall,
            "turns_completed": len(self.evaluations),
            "mastered": final_rubric.overall >= 0.80 or any(e.is_mastered for e in self.evaluations),
            "rubric": final_rubric,
            "all_misconceptions": list(set(all_misconceptions)),
            "all_jargon": list(set(all_jargon)),
        }
