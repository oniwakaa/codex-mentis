"""Teaching Session Engine — interactive guided learning.

State machine + LLM-backed response analysis + Rich UI widgets. Wired into
the chat REPL via the /explore command (see chat.py).
"""

from pitagora.teaching.analyzer import Classification, ResponseAnalyzer, ResponseClassification
from pitagora.teaching.session import StyleEffectiveness, TeachingSession, TeachingState
from pitagora.teaching.ui import (
    show_comprehension_gauge,
    show_controls,
    show_journey_map,
    show_session_summary,
    show_subconcept_progress,
    show_topic_overview,
)

__all__ = [
    "Classification",
    "ResponseAnalyzer",
    "ResponseClassification",
    "StyleEffectiveness",
    "TeachingSession",
    "TeachingState",
    "show_comprehension_gauge",
    "show_controls",
    "show_journey_map",
    "show_session_summary",
    "show_subconcept_progress",
    "show_topic_overview",
]
