"""ResponseAnalyzer — classify learner replies using LLM calls.

No keyword matching: every free-form reply is sent to the chat completion
endpoint with a strict instruction to return one of the canonical labels.
Single-character shortcuts bypass the LLM entirely (fast path).

Each classification maps to a comprehension delta applied by TeachingSession,
and tracks Bloom Cognitive Taxonomy levels and Cognitive Load.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class Classification(StrEnum):
    correct = "correct"
    partial = "partial"
    confused = "confused"
    skip = "skip"
    deeper = "deeper"
    different_style = "different_style"
    question = "question"
    off_topic = "off_topic"


class BloomLevel(StrEnum):
    recall = "recall"
    understand = "understand"
    apply = "apply"
    analyze = "analyze"
    evaluate = "evaluate"
    create = "create"


class CognitiveLoad(StrEnum):
    low = "low"
    optimal = "optimal"
    overloaded = "overloaded"


# Comprehension deltas per classification. Tunable; values chosen so a
# correct streak lifts mastery from 0 to ~0.8 in ~6 interactions.
DELTA: dict[str, float] = {
    Classification.correct.value: 0.15,
    Classification.partial.value: 0.05,
    Classification.confused.value: -0.20,
    Classification.skip.value: -0.05,
    Classification.deeper.value: 0.05,
    Classification.different_style.value: 0.0,
    Classification.question.value: 0.0,
    Classification.off_topic.value: -0.10,
}


@dataclass
class ResponseClassification:
    label: str
    delta: float
    rationale: str = ""
    via_shortcut: bool = False
    bloom_level: str = BloomLevel.understand.value
    cognitive_load: str = CognitiveLoad.optimal.value


# Shortcut → classification/action map. These skip the LLM round-trip entirely.
SHORTCUT_CLASSIFICATION: dict[str, str] = {
    "n": Classification.skip.value,
    "e": Classification.different_style.value,
    "d": Classification.deeper.value,
    "s": Classification.skip.value,
    "?": Classification.confused.value,
    "v": "visualize",
    "q": "quiz",
}


CLASSIFICATION_SYSTEM_PROMPT = (
    "You are a response classifier for an interactive teaching system. "
    "Given the learner's reply, the topic, and the current sub-concept, "
    "classify the reply into EXACTLY one of these labels:\n"
    "  correct     — the learner demonstrates understanding of the sub-concept\n"
    "  partial     — partially correct but missing a key piece\n"
    "  confused    — the learner is confused or holds a misconception\n"
    "  skip        — the learner wants to move on without answering\n"
    "  deeper      — the learner asks to go deeper or shows advanced understanding\n"
    "  different_style — the learner asks for a different explanation style\n"
    "  question    — the learner asks a clarifying question\n"
    "  off_topic   — the reply is unrelated to the sub-concept\n\n"
    "Optionally classify bloom_level (recall/understand/apply/analyze/evaluate/create) "
    "and cognitive_load (low/optimal/overloaded).\n\n"
    "Respond with ONLY a JSON object: "
    '{"label": "<one of the labels>", "rationale": "<one short sentence>", "bloom_level": "understand", "cognitive_load": "optimal"}. '
    "No extra text, no markdown fences."
)


class ResponseAnalyzer:
    """Classify learner responses. Uses the same chat_completion function
    the rest of the app uses (passed in to avoid a circular import)."""

    def __init__(self, chat_completion_fn) -> None:
        self._chat = chat_completion_fn

    def classify(
        self,
        reply: str,
        topic: str,
        sub_concept: str,
        config: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> ResponseClassification:
        # Fast path: single-character shortcut bypasses the LLM.
        label = SHORTCUT_CLASSIFICATION.get(reply.strip().lower())
        if label:
            load = CognitiveLoad.overloaded.value if label == Classification.confused.value else CognitiveLoad.optimal.value
            return ResponseClassification(
                label=label,
                delta=DELTA.get(label, 0.0),
                rationale="shortcut",
                via_shortcut=True,
                cognitive_load=load,
            )

        prompt = (
            f"Topic: {topic}\n"
            f"Sub-concept: {sub_concept}\n"
            f'Learner reply:\n"""\n{reply}\n"""\n\n'
            f"Classify the reply."
        )
        messages = [
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        try:
            raw = self._chat(messages, model=model, config=config)
            return self._parse(raw)
        except Exception as e:
            logger.warning("analyzer LLM call failed: %s — defaulting to partial", e)
            return ResponseClassification(
                label=Classification.partial.value,
                delta=DELTA[Classification.partial.value],
                rationale=f"analyzer_error: {e}",
            )

    @staticmethod
    def _parse(raw: str) -> ResponseClassification:
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("\n", 1)[-1] if "\n" in s else s
            if s.endswith("```"):
                s = s[:-3].strip()
        try:
            obj = json.loads(s)
            if not isinstance(obj, dict):
                raise json.JSONDecodeError("expected an object", s, 0)
            label = obj.get("label", "").strip().lower()
            if label not in DELTA:
                return ResponseClassification(
                    label=Classification.partial.value,
                    delta=DELTA[Classification.partial.value],
                    rationale=f"unknown_label: {label}",
                )
            bloom = obj.get("bloom_level", BloomLevel.understand.value).strip().lower()
            load = obj.get("cognitive_load", CognitiveLoad.optimal.value).strip().lower()
            return ResponseClassification(
                label=label,
                delta=DELTA[label],
                rationale=obj.get("rationale", "")[:200],
                bloom_level=bloom if bloom in [b.value for b in BloomLevel] else BloomLevel.understand.value,
                cognitive_load=load if load in [c.value for c in CognitiveLoad] else CognitiveLoad.optimal.value,
            )
        except json.JSONDecodeError:
            low = s.lower()
            for cand in DELTA:
                if cand in low:
                    return ResponseClassification(
                        label=cand, delta=DELTA[cand], rationale="salvaged"
                    )
            return ResponseClassification(
                label=Classification.partial.value,
                delta=DELTA[Classification.partial.value],
                rationale="unparseable",
            )
