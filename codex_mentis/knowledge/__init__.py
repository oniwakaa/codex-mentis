"""Web-acquired knowledge system for Codex Mentis.

Uses webfetch (firish/webfetch) as the free web search + crawling engine.
Instead of hardcoded concepts, agents discover knowledge by:
1. Searching the web via webfetch's multi-engine RRF fusion
2. Fetching and extracting papers/articles locally
3. Extracting equations, definitions, theorems, proofs
4. Building the concept graph dynamically from ingested material
5. Citing sources in every response

Install: pip install webfetch-llm
MCP: uvx webfetch-llm (runs as MCP server)
"""
from codex_mentis.knowledge.acquisition import KnowledgeAcquisition
from codex_mentis.knowledge.base import KnowledgeBase
from codex_mentis.knowledge.webfetch_bridge import WebfetchBridge
from codex_mentis.knowledge.extractor import KnowledgeExtractor

__all__ = [
    "KnowledgeAcquisition",
    "KnowledgeBase",
    "WebfetchBridge",
    "KnowledgeExtractor",
]
