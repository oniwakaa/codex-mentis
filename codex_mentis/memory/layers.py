from collections import deque
from typing import Dict, Any, List, Optional
from codex_mentis.agents.providers.base import BaseProvider
from codex_mentis.memory.store import MemoryStore

class ThreeLayerMemory:
    def __init__(self, store: MemoryStore, provider: Optional[BaseProvider] = None):
        """
        Manages the 3-Layer Memory System:
          - L1 (Session): Ephemeral rolling queue of recent message exchanges
          - L2 (Topic): Persisted summaries of topic-specific study/reason sessions
          - L3 (Synthesis): High-level cross-topic connections and long-term insights
        """
        self.store = store
        self.provider = provider
        self.l1: deque = deque(maxlen=15)
        self.current_conversation_id: Optional[str] = None

    def add_message(self, message: Dict[str, str], conversation_id: Optional[str] = None):
        """
        Adds a message {"role": "...", "content": "..."} to L1, and optionally saves
        the full conversation session to the DB.
        """
        self.l1.append(message)
        if conversation_id:
            self.current_conversation_id = conversation_id
            # Retrieve current conversation history, append, and save
            history = self.store.get_conversation(conversation_id) or []
            history.append(message)
            # Use topic from first message or default
            topic = "General"
            if len(history) > 0:
                # Truncate first message to get a topic suggestion
                topic = history[0].get("content", "General")[:30]
            self.store.save_conversation(conversation_id, topic, history)

    def summarize_session(self, topic: str) -> str:
        """
        Summarizes the recent message exchanges from L1 (Session) and commits it
        as an L2 (Topic) memory in the store.
        """
        if not self.l1:
            return "No messages in session to summarize."

        chat_history = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in self.l1])
        prompt = (
            f"Below is a chat session transcript on the topic of '{topic}'. "
            f"Summarize the key mathematical formulas, physical concepts, and reasoning paths. "
            f"Keep it concise but ensure formulas are preserved in LaTeX:\n\n"
            f"{chat_history}"
        )
        
        summary = ""
        if self.provider:
            try:
                resp = self.provider.complete([{"role": "user", "content": prompt}])
                summary = resp.get("content", "")
            except Exception as e:
                summary = f"Error generating summary: {str(e)}"
        
        if not summary:
            # Fallback simple description
            summary = f"Summary of session about {topic} containing {len(self.l1)} messages."

        # Save to L2 topic memory
        self.store.save(layer="L2", content=summary, topic=topic)
        return summary

    def synthesize_topics(self, topics: List[str]) -> str:
        """
        Gathers L2 summaries for the listed topics and produces cross-topic synthesis (L3).
        """
        l2_summaries = []
        for topic in topics:
            mems = self.store.retrieve(topic, layer="L2", top_k=2)
            for m in mems:
                l2_summaries.append(f"Topic: {m['topic']}\nSummary: {m['content']}")

        if not l2_summaries:
            return "No topic summaries found to synthesize."

        summaries_text = "\n\n".join(l2_summaries)
        prompt = (
            f"You are synthesizing knowledge across these topics: {', '.join(topics)}.\n"
            f"Here are the topic summaries:\n\n{summaries_text}\n\n"
            f"Identify cross-topic connections, unifying principles, or mathematical mappings "
            f"between these fields. Format the output with clear headers and LaTeX formulas."
        )

        synthesis = ""
        if self.provider:
            try:
                resp = self.provider.complete([{"role": "user", "content": prompt}])
                synthesis = resp.get("content", "")
            except Exception as e:
                synthesis = f"Error generating synthesis: {str(e)}"

        if not synthesis:
            synthesis = f"Synthesis of topics: {', '.join(topics)}. Connections identified between fields."

        # Save to L3 synthesis memory
        self.store.save(layer="L3", content=synthesis, topic=",".join(topics))
        return synthesis

    def get_context(self, query: str) -> str:
        """
        Returns relevant context from L1 (Session), L2 (Topic), and L3 (Synthesis) for a query.
        """
        context_blocks = []

        # 1. Ephemeral context (recent chats)
        if self.l1:
            recent_chats = []
            for msg in list(self.l1)[-6:]:  # last 6 messages
                recent_chats.append(f"{msg['role']}: {msg['content']}")
            context_blocks.append("### Ephemeral Conversation Context (L1):\n" + "\n".join(recent_chats))

        # 2. Topic-specific context (L2)
        l2_mems = self.store.retrieve(query, layer="L2", top_k=2)
        if l2_mems:
            l2_lines = []
            for m in l2_mems:
                l2_lines.append(f"Topic Summary [{m['topic']}]: {m['content']}")
            context_blocks.append("### Relevant Topic Context (L2):\n" + "\n".join(l2_lines))

        # 3. Synthesized insights (L3)
        l3_mems = self.store.retrieve(query, layer="L3", top_k=1)
        if l3_mems:
            l3_lines = []
            for m in l3_mems:
                l3_lines.append(f"Global Synthesis insight: {m['content']}")
            context_blocks.append("### Synthesized Knowledge Context (L3):\n" + "\n".join(l3_lines))

        return "\n\n".join(context_blocks)
