class ContextManager:
    """Manages context window budget and compaction."""

    def __init__(self, max_tokens: int = 128000, compaction_threshold: float = 0.80):
        self.max_tokens = max_tokens
        self.compaction_threshold = compaction_threshold

    def estimate_tokens(self, messages: list[dict]) -> int:
        """Estimate token count for message array (~4 chars per token)."""
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return total_chars // 4

    def needs_compaction(self, messages: list[dict]) -> bool:
        """Check if context exceeds compaction threshold."""
        return self.estimate_tokens(messages) > self.max_tokens * self.compaction_threshold

    def compact(self, messages: list[dict], keep_recent: int = 10) -> list[dict]:
        """Compact message history:

        1. Keep system prompt and first user message (first 2 messages)
        2. Summarize older tool results into a single message
        3. Keep the last `keep_recent` messages verbatim
        """
        if len(messages) <= keep_recent + 2:
            return messages

        system_and_first = messages[:2]  # system prompt + first user message
        to_summarize = messages[2:-keep_recent]
        recent = messages[-keep_recent:]

        summary_parts = []
        for msg in to_summarize:
            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))[:200]
            summary_parts.append(f"[{role}] {content}")

        summary_msg = {
            "role": "system",
            "content": f"[Compacted context — {len(to_summarize)} messages summarized]\n"
            + "\n---\n".join(summary_parts),
        }

        return system_and_first + [summary_msg] + recent
