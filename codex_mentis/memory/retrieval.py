from typing import Dict, Any, List, Optional
from codex_mentis.memory.store import MemoryStore

class MemoryRetriever:
    def __init__(self, store: MemoryStore):
        self.store = store

    def search(
        self, 
        query: str, 
        top_k: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Run semantic search over all memories, applying topic, layer, or metadata filters.
        """
        layer_filter = filters.get("layer") if filters else None
        
        # Pull candidate list from store
        candidates = self.store.retrieve(query, layer=layer_filter, top_k=top_k * 3)
        
        # Apply other custom filters
        filtered_results = []
        for cand in candidates:
            keep = True
            if filters:
                # Check topic filter
                if "topic" in filters and cand["topic"].lower() != filters["topic"].lower():
                    keep = False
                # Check arbitrary metadata filters
                for k, v in filters.items():
                    if k not in ("layer", "topic"):
                        if cand["metadata"].get(k) != v:
                            keep = False
            if keep:
                filtered_results.append(cand)
                
        return filtered_results[:top_k]

    def get_relevant_context(self, query: str, max_tokens: int = 1500) -> str:
        """
        Finds relevant context and formats it as a single string,
        respecting the token limit (estimating 4 characters per token).
        """
        max_chars = max_tokens * 4
        mems = self.search(query, top_k=6)
        
        if not mems:
            return "No relevant memories found."

        context_lines = []
        current_len = 0
        
        for m in mems:
            score_pct = m["score"] * 100
            block = (
                f"--- Memory Block (Layer: {m['layer']}, Topic: {m['topic']}, Relevance: {score_pct:.1f}%) ---\n"
                f"{m['content']}\n"
                f"Timestamp: {m['timestamp']}\n"
            )
            
            if current_len + len(block) > max_chars:
                # If we exceed max length, try to truncate the last block or break
                remaining = max_chars - current_len
                if remaining > 100:
                    context_lines.append(block[:remaining] + "... [TRUNCATED DUE TO CONTEXT LIMIT]")
                break
                
            context_lines.append(block)
            current_len += len(block)
            
        return "\n".join(context_lines)
