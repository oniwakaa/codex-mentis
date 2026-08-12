"""Web-acquired knowledge system for Pitagora.

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
from pitagora.knowledge.acquisition import KnowledgeAcquisition
from pitagora.knowledge.base import KnowledgeBase
from pitagora.knowledge.webfetch_bridge import WebfetchBridge
from pitagora.knowledge.extractor import KnowledgeExtractor

__all__ = [
    "KnowledgeAcquisition",
    "KnowledgeBase",
    "WebfetchBridge",
    "KnowledgeExtractor",
]
