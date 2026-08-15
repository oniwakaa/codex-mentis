"""Pitagora chat package."""

from pitagora.chat.controller import ChatController
from pitagora.chat.renderer import ChatRenderer
from pitagora.chat.runtime import (
    STYLE_GUIDES,
    SUBCONCEPT_GEN_PROMPT,
    _build_feedback_loop,
    _build_teaching_prompt,
    _check_due_reviews,
    _dispatch_rich_events,
    _generate_sub_concepts,
    _get_concept_context,
    _get_memory_context,
    _get_rag_context,
    _get_user_context,
    _record_study,
    _render_rich_event,
    _save_to_memory,
    _seed_session_style,
    _verify_math,
    chat_completion,
    launch_chat,
    load_provider_config,
)
from pitagora.chat.session import ChatEvent, ChatSessionState

__all__ = [
    "ChatController",
    "ChatEvent",
    "ChatSessionState",
    "ChatRenderer",
    "load_provider_config",
    "chat_completion",
    "launch_chat",
    "_build_feedback_loop",
    "_seed_session_style",
    "_get_rag_context",
    "_get_concept_context",
    "_get_memory_context",
    "_get_user_context",
    "_verify_math",
    "_save_to_memory",
    "_record_study",
    "_check_due_reviews",
    "_generate_sub_concepts",
    "_build_teaching_prompt",
    "_render_rich_event",
    "_dispatch_rich_events",
    "SUBCONCEPT_GEN_PROMPT",
    "STYLE_GUIDES",
]

