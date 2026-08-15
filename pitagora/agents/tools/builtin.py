"""Builtin tools registered with ToolRegistry."""

from pitagora.agents.tools.registry import ToolRegistry, ToolSpec


async def _search_knowledge(query: str, limit: int = 3) -> dict:
    from pitagora.knowledge.base import KnowledgeBase

    kb = KnowledgeBase()
    results = kb.search(query, limit=limit)
    return {"query": query, "results": results}


async def _evaluate_expression(expression: str) -> dict:
    from pitagora.math_engine.sandbox import SymPySandbox

    sandbox = SymPySandbox()
    res = sandbox.evaluate(expression)
    return {
        "expression": expression,
        "verified": res.verified,
        "value": res.value,
        "error": res.error,
    }


async def _plot_function(expression: str) -> dict:
    from pitagora.math_engine.plots import MathPlotter

    plotter = MathPlotter()
    plotter.plot_function(expression, (-10.0, 10.0))
    return {"expression": expression, "status": "plotted"}


async def _fetch_web_content(url: str) -> dict:
    from pitagora.knowledge.webfetch_bridge import WebfetchBridge

    bridge = WebfetchBridge()
    text = bridge.fetch_url(url) if hasattr(bridge, "fetch_url") else f"Fetched {url}"
    return {"url": url, "content": str(text)[:2000]}


async def _get_concept_status(concept: str) -> dict:
    from pitagora.concepts.tracker import MasteryTracker

    tracker = MasteryTracker()
    status = tracker.get_mastery(concept) if hasattr(tracker, "get_mastery") else 0.0
    return {"concept": concept, "status": status}


async def _get_memory_items(query: str, limit: int = 5) -> dict:
    from pitagora.memory.store import MemoryStore

    store = MemoryStore()
    entries = store.list_memories(limit=limit)
    return {
        "query": query,
        "entries": [e.to_dict() if hasattr(e, "to_dict") else str(e) for e in entries],
    }


async def _update_concept_mastery(concept: str, mastery: float) -> dict:
    from pitagora.concepts.tracker import MasteryTracker

    tracker = MasteryTracker()
    if hasattr(tracker, "update_mastery"):
        tracker.update_mastery(concept, mastery)
    return {"concept": concept, "mastery": mastery, "status": "updated"}


async def _store_memory(content: str, topic: str = "general") -> dict:
    from pitagora.core.models import MemoryEntry
    from pitagora.memory.store import MemoryStore

    store = MemoryStore()
    entry = MemoryEntry(layer="L1", content=content, topic=topic)
    entry_id = store.create_memory_entry(entry)
    return {"id": entry_id, "topic": topic, "status": "stored"}


async def _create_journey(topic: str, sub_concepts: list[str]) -> dict:
    from pitagora.journeys.store import get_or_create_journey

    journey = get_or_create_journey(topic, sub_concepts)
    return {"id": journey.id, "topic": journey.topic, "status": journey.status}


async def _delegate_to_agent(agent_name: str, task: str) -> dict:
    from pitagora.agents.orchestrator import Orchestrator

    orch = Orchestrator(agents={})
    resp = orch.process(task, mode="study") if hasattr(orch, "process") else None
    return {
        "agent_name": agent_name,
        "task": task,
        "response": resp.content if resp else "no response",
    }


def register_builtin_tools(registry: ToolRegistry) -> None:
    """Register all builtin tools into registry."""
    tools = [
        ToolSpec(
            name="search_knowledge",
            description="Search the knowledge base for documents.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
            required_permission="read",
            category="file",
            handler=_search_knowledge,
        ),
        ToolSpec(
            name="evaluate_expression",
            description="Evaluate a mathematical expression securely with SymPy.",
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                },
                "required": ["expression"],
            },
            required_permission="read",
            category="math",
            handler=_evaluate_expression,
        ),
        ToolSpec(
            name="plot_function",
            description="Generate ASCII plot for a math function.",
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                },
                "required": ["expression"],
            },
            required_permission="read",
            category="math",
            handler=_plot_function,
        ),
        ToolSpec(
            name="fetch_web_content",
            description="Fetch web page content.",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                },
                "required": ["url"],
            },
            required_permission="read",
            category="web",
            handler=_fetch_web_content,
        ),
        ToolSpec(
            name="get_concept_status",
            description="Get user mastery status for a concept.",
            input_schema={
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                },
                "required": ["concept"],
            },
            required_permission="read",
            category="memory",
            handler=_get_concept_status,
        ),
        ToolSpec(
            name="get_memory_items",
            description="Search memory entries.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
            required_permission="read",
            category="memory",
            handler=_get_memory_items,
        ),
        ToolSpec(
            name="update_concept_mastery",
            description="Update user concept mastery score.",
            input_schema={
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "mastery": {"type": "number"},
                },
                "required": ["concept", "mastery"],
            },
            required_permission="write",
            category="memory",
            handler=_update_concept_mastery,
        ),
        ToolSpec(
            name="store_memory",
            description="Store a new memory entry.",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "topic": {"type": "string"},
                },
                "required": ["content"],
            },
            required_permission="write",
            category="memory",
            handler=_store_memory,
        ),
        ToolSpec(
            name="create_journey",
            description="Create or get a learning journey.",
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "sub_concepts": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["topic", "sub_concepts"],
            },
            required_permission="write",
            category="memory",
            handler=_create_journey,
        ),
        ToolSpec(
            name="delegate_to_agent",
            description="Delegate task to a specialized agent.",
            input_schema={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "task": {"type": "string"},
                },
                "required": ["agent_name", "task"],
            },
            required_permission="admin",
            category="agent",
            handler=_delegate_to_agent,
        ),
    ]

    for tool in tools:
        registry.register(tool)
