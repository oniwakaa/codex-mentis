"""MCP tool definitions and handlers for Pitagora."""

from typing import Any


async def handle_pitagora_solve(problem: str, mode: str = "derive") -> dict[str, Any]:
    """Solve or derive a mathematical / physics problem."""
    from pitagora.math_engine.sandbox import SymPySandbox

    sandbox = SymPySandbox()
    res = sandbox.evaluate(problem)
    return {
        "problem": problem,
        "mode": mode,
        "verified": res.verified,
        "value": res.value,
        "error": res.error,
    }


async def handle_pitagora_verify(expression: str) -> dict[str, Any]:
    """Verify mathematical expression with SymPy sandbox."""
    from pitagora.math_engine.sandbox import SymPySandbox

    sandbox = SymPySandbox()
    res = sandbox.evaluate(expression)
    return {
        "expression": expression,
        "verified": res.verified,
        "value": res.value,
        "error": res.error,
    }


async def handle_pitagora_explain(topic: str, level: str = "intermediate") -> dict[str, Any]:
    """Generate Feynman explanation for a topic."""
    explanation = f"Explanation of '{topic}' at level '{level}': Using Feynman technique, breaking down into fundamental concepts."
    return {"topic": topic, "level": level, "explanation": explanation}


async def handle_pitagora_concept_status(concept: str) -> dict[str, Any]:
    """Get mastery status for a concept."""
    from pitagora.concepts.tracker import MasteryTracker

    tracker = MasteryTracker()
    mastery = tracker.get_mastery(concept) if hasattr(tracker, "get_mastery") else 0.0
    return {"concept": concept, "mastery_score": mastery}


MCP_TOOLS = {
    "pitagora_solve": {
        "description": "Derive or solve a mathematical or physics problem securely.",
        "input_schema": {
            "type": "object",
            "properties": {
                "problem": {"type": "string"},
                "mode": {"type": "string"},
            },
            "required": ["problem"],
        },
        "handler": handle_pitagora_solve,
    },
    "pitagora_verify": {
        "description": "Verify a mathematical claim or expression.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
        "handler": handle_pitagora_verify,
    },
    "pitagora_explain": {
        "description": "Explain a concept using the Feynman technique.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "level": {"type": "string"},
            },
            "required": ["topic"],
        },
        "handler": handle_pitagora_explain,
    },
    "pitagora_concept_status": {
        "description": "Check user mastery status for a concept.",
        "input_schema": {
            "type": "object",
            "properties": {"concept": {"type": "string"}},
            "required": ["concept"],
        },
        "handler": handle_pitagora_concept_status,
    },
}
