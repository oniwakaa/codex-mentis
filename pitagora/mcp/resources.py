"""MCP resource definitions and handlers for Pitagora."""

from typing import Any


async def handle_read_concept_resource(concept: str) -> dict[str, Any]:
    """Resource handler for pitagora://concepts/{concept}."""
    from pitagora.concepts.tracker import MasteryTracker

    tracker = MasteryTracker()
    mastery = tracker.get_mastery(concept) if hasattr(tracker, "get_mastery") else 0.0
    return {
        "uri": f"pitagora://concepts/{concept}",
        "concept": concept,
        "mastery_score": mastery,
    }


async def handle_read_journey_resource(journey_id: str) -> dict[str, Any]:
    """Resource handler for pitagora://journeys/{id}."""
    from pitagora.journeys.store import load_journey

    journey = load_journey(journey_id)
    if journey:
        return {
            "uri": f"pitagora://journeys/{journey_id}",
            "journey": journey.to_dict() if hasattr(journey, "to_dict") else str(journey),
        }
    return {
        "uri": f"pitagora://journeys/{journey_id}",
        "error": "Journey not found",
    }


async def handle_read_memory_stats_resource() -> dict[str, Any]:
    """Resource handler for pitagora://memory/stats."""
    from pitagora.memory.store import MemoryStore

    store = MemoryStore()
    memories = store.list_memories()
    return {
        "uri": "pitagora://memory/stats",
        "total_memories": len(memories),
    }


MCP_RESOURCES = {
    "pitagora://concepts/{concept}": {
        "name": "Concept Mastery Status",
        "description": "Returns concept mastery score and metadata.",
        "handler": handle_read_concept_resource,
    },
    "pitagora://journeys/{id}": {
        "name": "Learning Journey Details",
        "description": "Returns status and progress of a learning journey.",
        "handler": handle_read_journey_resource,
    },
    "pitagora://memory/stats": {
        "name": "Memory Store Statistics",
        "description": "Returns aggregate memory layer statistics.",
        "handler": handle_read_memory_stats_resource,
    },
}
