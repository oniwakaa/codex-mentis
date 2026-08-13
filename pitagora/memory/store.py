import json
import os
import shutil
import struct
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from sqlite_utils import Database
from pitagora.core.models import MemoryEntry
from pitagora.core.constants import MEMORY_DB

# Import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False

class TfidfFallbackEmbedder:
    def __init__(self, n_features: int = 384):
        """
        Fallback embedder using HashingVectorizer to perform stateless,
        consistent text vectorization without needing a fitted corpus.
        """
        from sklearn.feature_extraction.text import HashingVectorizer
        self.vectorizer = HashingVectorizer(n_features=n_features, alternate_sign=False)

    def encode(self, text: Any) -> Any:
        if isinstance(text, str):
            sparse_matrix = self.vectorizer.transform([text])
            dense = sparse_matrix.toarray()[0]
            # Normalize
            norm = sum(x*x for x in dense) ** 0.5
            if norm > 0:
                dense = [x / norm for x in dense]
            return list(dense)
        else:
            # list of strings
            sparse_matrix = self.vectorizer.transform(text)
            dense = sparse_matrix.toarray()
            results = []
            for row in dense:
                norm = sum(x*x for x in row) ** 0.5
                if norm > 0:
                    row = [x / norm for x in row]
                results.append(list(row))
            return results

class MockEmbedder:
    def encode(self, text: str) -> List[float]:
        """
        Basic hash-based feature extraction trick if even scikit-learn is missing.
        """
        import hashlib
        import re
        
        words = re.findall(r"\w+", text.lower())
        vector = [0.0] * 384
        
        if not words:
            vector[0] = 1.0
            return vector
            
        for word in words:
            h = int(hashlib.md5(word.encode('utf-8')).hexdigest()[:8], 16)
            idx = h % 384
            vector[idx] += 1.0
            
        # Normalize
        norm = sum(x*x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]
            
        return vector

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(x * y for x, y in zip(v1, v2))
    norm_v1 = sum(x * x for x in v1) ** 0.5
    norm_v2 = sum(x * x for x in v2) ** 0.5
    if norm_v1 * norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)

class MemoryStore:
    def __init__(self, db_path: str = str(MEMORY_DB)):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize Embedder
        self.embedder = None
        if EMBEDDER_AVAILABLE:
            try:
                self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception:
                pass
        
        if self.embedder is None:
            try:
                self.embedder = TfidfFallbackEmbedder()
            except Exception:
                self.embedder = MockEmbedder()
                
        self._init_db()

    def _init_db(self):
        db = Database(self.db_path)
        
        # Table: memory_entries
        if not db["memory_entries"].exists():
            db["memory_entries"].create({
                "id": int,
                "layer": str,
                "content": str,
                "topic": str,
                "embedding": bytes, # BLOB
                "timestamp": str,
                "metadata": str # JSON text
            }, pk="id")
            db["memory_entries"].create_index(["layer"])
            db["memory_entries"].create_index(["topic"])

        # Table: conversations
        if not db["conversations"].exists():
            db["conversations"].create({
                "id": str,
                "topic": str,
                "messages": str, # JSON text
                "created_at": str
            }, pk="id")

    def _float_list_to_blob(self, floats: List[float]) -> bytes:
        return struct.pack(f"{len(floats)}f", *floats)

    def _blob_to_float_list(self, blob: bytes) -> List[float]:
        n = len(blob) // 4
        return list(struct.unpack(f"{n}f", blob))

    def get_embedding(self, text: str) -> List[float]:
        # Encode text as embedding vector
        vector = self.embedder.encode(text)
        if hasattr(vector, "tolist"):
            return vector.tolist()
        return list(vector)

    # --- Full CRUD operations ---
    def create_memory_entry(self, entry: MemoryEntry) -> int:
        """Create a new memory entry."""
        db = Database(self.db_path)
        vector = entry.embedding
        if not vector:
            vector = self.get_embedding(entry.content)
        embedding_blob = self._float_list_to_blob(vector)
        metadata_str = json.dumps(entry.metadata or {})
        
        row = {
            "layer": entry.layer,
            "content": entry.content,
            "topic": entry.topic,
            "embedding": embedding_blob,
            "metadata": metadata_str
        }
        if entry.timestamp:
            row["timestamp"] = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
        table = db["memory_entries"]
        table.insert(row)
        return table.last_pk

    def get_memory_entry(self, entry_id: int) -> Optional[MemoryEntry]:
        """Read a memory entry by ID."""
        db = Database(self.db_path)
        try:
            row = db["memory_entries"].get(entry_id)
            return MemoryEntry(
                id=row["id"],
                layer=row["layer"],
                content=row["content"],
                topic=row["topic"],
                embedding=self._blob_to_float_list(row["embedding"]),
                timestamp=datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S") if row.get("timestamp") else datetime.now(),
                metadata=json.loads(row["metadata"] or "{}")
            )
        except Exception:
            return None

    def update_memory_entry(self, entry_id: int, entry: MemoryEntry) -> bool:
        """Update an existing memory entry."""
        db = Database(self.db_path)
        if not db["memory_entries"].exists():
            return False
        try:
            row = {}
            if entry.layer:
                row["layer"] = entry.layer
            if entry.content:
                row["content"] = entry.content
                vector = entry.embedding or self.get_embedding(entry.content)
                row["embedding"] = self._float_list_to_blob(vector)
            if entry.topic:
                row["topic"] = entry.topic
            if entry.metadata:
                row["metadata"] = json.dumps(entry.metadata)
            if entry.timestamp:
                row["timestamp"] = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                
            db["memory_entries"].update(entry_id, row)
            return True
        except Exception:
            return False

    def delete_memory_entry(self, entry_id: int) -> bool:
        """Delete a memory entry by ID."""
        db = Database(self.db_path)
        try:
            db["memory_entries"].delete(entry_id)
            return True
        except Exception:
            return False

    def list_memories(self, layer: Optional[str] = None, topic: Optional[str] = None) -> List[MemoryEntry]:
        """Lists memories with optional filters."""
        db = Database(self.db_path)
        where_clauses = []
        params = []
        if layer:
            where_clauses.append("layer = ?")
            params.append(layer)
        if topic:
            where_clauses.append("topic = ?")
            params.append(topic)
            
        if where_clauses:
            rows = db["memory_entries"].rows_where(" AND ".join(where_clauses), params)
        else:
            rows = db["memory_entries"].rows
            
        results = []
        for row in rows:
            results.append(MemoryEntry(
                id=row["id"],
                layer=row["layer"],
                content=row["content"],
                topic=row["topic"],
                embedding=self._blob_to_float_list(row["embedding"]),
                timestamp=datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S") if row.get("timestamp") else datetime.now(),
                metadata=json.loads(row["metadata"] or "{}")
            ))
        return results

    # --- Legacy/compatibility CRUD interface ---
    def save(
        self, 
        layer: str, 
        content: str, 
        topic: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        entry = MemoryEntry(
            layer=layer,
            content=content,
            topic=topic,
            metadata=metadata or {}
        )
        return self.create_memory_entry(entry)

    def retrieve(
        self, 
        query: str, 
        layer: Optional[str] = None, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        query_vector = self.get_embedding(query)
        db = Database(self.db_path)
        
        if layer:
            rows = list(db["memory_entries"].rows_where("layer = ?", [layer]))
        else:
            rows = list(db["memory_entries"].rows)
            
        results = []
        for row in rows:
            m_vector = self._blob_to_float_list(row["embedding"])
            similarity = cosine_similarity(query_vector, m_vector)
            
            results.append({
                "id": row["id"],
                "layer": row["layer"],
                "content": row["content"],
                "topic": row["topic"],
                "timestamp": row["timestamp"],
                "metadata": json.loads(row["metadata"] or "{}"),
                "score": similarity
            })
            
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def save_conversation(self, conversation_id: str, topic: str, messages: List[Dict[str, str]]):
        db = Database(self.db_path)
        messages_json = json.dumps(messages)
        db["conversations"].insert({
            "id": conversation_id,
            "topic": topic,
            "messages": messages_json,
            "created_at": datetime.now().isoformat()
        }, replace=True)

    def get_conversation(self, conversation_id: str) -> Optional[List[Dict[str, str]]]:
        db = Database(self.db_path)
        try:
            row = db["conversations"].get(conversation_id)
            return json.loads(row["messages"])
        except Exception:
            return None

    def get_topic_history(self, topic: str) -> List[Dict[str, Any]]:
        db = Database(self.db_path)
        rows = list(db["memory_entries"].rows_where("topic = ?", [topic]))
        return [
            {"id": row["id"], "layer": row["layer"], "content": row["content"], "timestamp": row["timestamp"]}
            for row in rows
        ]

    def get_review_queue(self) -> List[Dict[str, Any]]:
        db = Database(self.db_path)
        rows = list(db["memory_entries"].rows)
        now = datetime.now().date()
        queue = []
        for row in rows:
            meta = json.loads(row["metadata"] or "{}")
            next_review_str = meta.get("next_review")
            if next_review_str:
                try:
                    next_review = datetime.strptime(next_review_str, "%Y-%m-%d").date()
                    if next_review <= now:
                        queue.append({
                            "id": row["id"],
                            "layer": row["layer"],
                            "content": row["content"],
                            "topic": row["topic"],
                            "metadata": meta
                        })
                except ValueError:
                    pass
        return queue

    # --- Layer promotion and synthesis ---
    def promote_l1_to_l2(self, conversation_id: str, provider: Optional[Any] = None) -> Optional[int]:
        """Summarize conversation L1 messages and promote to L2 memory."""
        messages = self.get_conversation(conversation_id)
        if not messages:
            return None
            
        topic = "General"
        db = Database(self.db_path)
        try:
            conv = db["conversations"].get(conversation_id)
            topic = conv["topic"]
        except Exception:
            pass
            
        chat_history = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in messages])
        prompt = (
            f"Below is a chat session transcript on the topic of '{topic}'. "
            f"Summarize the key mathematical formulas, physical concepts, and reasoning paths. "
            f"Keep it concise but ensure formulas are preserved in LaTeX:\n\n"
            f"{chat_history}"
        )
        
        summary = ""
        if provider:
            try:
                resp = provider.complete([{"role": "user", "content": prompt}])
                summary = resp.get("content", "")
            except Exception as e:
                summary = f"Error generating summary: {str(e)}"
                
        if not summary:
            summary = f"Summary of session about {topic} containing {len(messages)} messages."
            
        return self.save(layer="L2", content=summary, topic=topic)

    def synthesize_l2_to_l3(self, topics: List[str], provider: Optional[Any] = None) -> Optional[int]:
        """Gather L2 memories across topics and synthesize into L3 insights."""
        l2_summaries = []
        for topic in topics:
            mems = self.retrieve(topic, layer="L2", top_k=2)
            for m in mems:
                l2_summaries.append(f"Topic: {m['topic']}\nSummary: {m['content']}")
                
        if not l2_summaries:
            return None
            
        summaries_text = "\n\n".join(l2_summaries)
        prompt = (
            f"You are synthesizing knowledge across these topics: {', '.join(topics)}.\n"
            f"Here are the topic summaries:\n\n{summaries_text}\n\n"
            f"Identify cross-topic connections, unifying principles, or mathematical mappings "
            f"between these fields. Format the output with clear headers and LaTeX formulas."
        )
        
        synthesis = ""
        if provider:
            try:
                resp = provider.complete([{"role": "user", "content": prompt}])
                synthesis = resp.get("content", "")
            except Exception as e:
                synthesis = f"Error generating synthesis: {str(e)}"
                
        if not synthesis:
            synthesis = f"Synthesis of topics: {', '.join(topics)}. Connections identified between fields."
            
        return self.save(layer="L3", content=synthesis, topic=",".join(topics))

    # --- Backup & Export ---
    def backup_database(self, dest_path: str) -> bool:
        """Create a backup copy of the SQLite database."""
        try:
            dest_path = os.path.expanduser(dest_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(self.db_path, dest_path)
            return True
        except Exception:
            return False

    def export_memories(self, dest_path: str) -> bool:
        """Export all memories as a JSON file."""
        try:
            dest_path = os.path.expanduser(dest_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            db = Database(self.db_path)
            memories = list(db["memory_entries"].rows)
            for mem in memories:
                if "embedding" in mem and mem["embedding"]:
                    mem["embedding"] = self._blob_to_float_list(mem["embedding"])
            
            with open(dest_path, "w", encoding="utf-8") as f:
                json.dump(memories, f, indent=2, default=str)
            return True
        except Exception:
            return False
