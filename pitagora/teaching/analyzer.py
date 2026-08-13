"""ResponseAnalyzer — classify learner replies using LLM calls.

No keyword matching: every free-form reply is sent to the chat completion
endpoint with a strict instruction to return one of the canonical labels.
Single-character shortcuts bypass the LLM entirely (fast path).

Each classification maps to a comprehension delta applied by TeachingSession.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Classification(str, Enum):
    correct = "correct"
    partial = "partial"
    confused = "confused"
    skip = "skip"
    deeper = "deeper"
    question = "question"
    off_topic = "off_topic"


# Comprehension deltas per classification. Tunable; values chosen so a
# correct streak lifts mastery from 0 to ~0.8 in ~6 interactions.
DELTA: Dict[str, float] = {
    Classification.correct.value: 0.15,
    Classification.partial.value: 0.05,
    Classification.confused.value: -0.20,
    Classification.skip.value: -0.05,
    Classification.deeper.value: 0.05,
    Classification.question.value: 0.0,
    Classification.off_topic.value: -0.10,
}


@dataclass
class ResponseClassification:
    label: str
    delta: float
    rationale: str = ""
    via_shortcut: bool = False


# Shortcut → classification map. These skip the LLM round-trip entirely.
# Note: "n" is intentionally absent — it maps to "next" in TeachingSession.SHORTCUTS
# and is handled by the session as an advance action, not a classification.
SHORTCUT_CLASSIFICATION: Dict[str, str] = {
    "e": Classification.partial.value,    # "explain differently" = didn't land
    "d": Classification.deeper.value,     # "go deeper" = ready for more
    "s": Classification.skip.value,
    "?": Classification.confused.value,
    "v": Classification.deeper.value,    # visualize = engagement
    "q": Classification.deeper.value,     # quiz request = engagement
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
    "  question    — the learner asks a clarifying question\n"
    "  off_topic   — the reply is unrelated to the sub-concept\n\n"
    "Respond with ONLY a JSON object: "
    '{"label": "<one of the labels>", "rationale": "<one short sentence>"}. '
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
        config: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
    ) -> ResponseClassification:
        # Fast path: single-character shortcut bypasses the LLM.
        label = SHORTCUT_CLASSIFICATION.get(reply.strip().lower())
        if label:
            return ResponseClassification(
                label=label,
                delta=DELTA[label],
                rationale="shortcut",
                via_shortcut=True,
            )

        prompt = (
            f"Topic: {topic}\n"
            f"Sub-concept: {sub_concept}\n"
            f"Learner reply:\n\"\"\"\n{reply}\n\"\"\"\n\n"
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
            # ponytail: fail soft to partial so the loop keeps moving. Add
            # retry/backoff if the provider flakes mid-session.
            return ResponseClassification(
                label=Classification.partial.value,
                delta=DELTA[Classification.partial.value],
                rationale=f"analyzer_error: {e}",
            )

    @staticmethod
    def _parse(raw: str) -> ResponseClassification:
        # Strip markdown fences if present
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("\n", 1)[-1] if "\n" in s else s
            if s.endswith("```"):
                s = s[:-3].strip()
        try:
            obj = json.loads(s)
            label = obj.get("label", "").strip().lower()
            if label not in DELTA:
                # Unknown label → treat as partial (don't trust a hallucinated tag).
                return ResponseClassification(
                    label=Classification.partial.value,
                    delta=DELTA[Classification.partial.value],
                    rationale=f"unknown_label: {label}",
                )
            return ResponseClassification(
                label=label,
                delta=DELTA[label],
                rationale=obj.get("rationale", "")[:200],
            )
        except json.JSONDecodeError:
            # Try to salvage a bare label word.
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


def demo() -> None:
    """Self-check: shortcut path + parser robustness, no network needed."""

    def fake_chat(messages, model=None, config=None):
        return '{"label": "correct", "rationale": "nailed it"}'

    a = ResponseAnalyzer(fake_chat)
    # "n" is no longer a classification shortcut (handled by session as "next"),
    # so it now goes through the LLM path.
    r = a.classify("n", "limits", "definition")
    assert not r.via_shortcut and r.label == "correct"
    r = a.classify("The limit is the value the function approaches.",
                   "limits", "definition")
    assert r.label == "correct" and r.delta == 0.15

    # Salvage path
    def fence_chat(messages, model=None, config=None):
        return "```json\n{\"label\": \"confused\"}\n```"
    a2 = ResponseAnalyzer(fence_chat)
    r2 = a2.classify("huh?", "limits", "definition")
    assert r2.label == "confused"
    print("analyzer demo ok")


if __name__ == "__main__":
    demo()
