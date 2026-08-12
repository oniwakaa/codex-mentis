"""Teaching Session Engine — interactive guided learning.

State machine + LLM-backed response analysis + Rich UI widgets. Wired into
the chat REPL via the /explore command (see chat.py).
"""
from pitagora.teaching.session import TeachingSession, TeachingState, StyleEffectiveness
from pitagora.teaching.analyzer import ResponseAnalyzer, ResponseClassification, Classification
from pitagora.teaching.ui import (
    show_controls,
    show_comprehension_gauge,
    show_subconcept_progress,
    show_topic_overview,
    show_session_summary,
    show_journey_map,
)

__all__ = [
    "TeachingSession",
    "TeachingState",
    "StyleEffectiveness",
    "ResponseAnalyzer",
    "ResponseClassification",
    "Classification",
    "show_controls",
    "show_comprehension_gauge",
    "show_subconcept_progress",
    "show_topic_overview",
    "show_session_summary",
    "show_journey_map",
]
