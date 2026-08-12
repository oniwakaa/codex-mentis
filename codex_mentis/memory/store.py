import json
import sqlite3
import os
import struct
import datetime
from typing import Dict, Any, List, Optional, Tuple

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False

class MockEmbedder:
    def encode(self, text: str) -> List[float]:
        """
        Feature-hashing (hashing trick) bag-of-words embedder.
        Provides a real keyword-overlap vector space model!
        """
        import hashlib
        import re
        
        words = re.findall(r"\w+", text.lower())
        vector = [0.0] * 384
        
        if not words:
            vector[0] = 1.0
            return vector
            
        for word in words:
            # Hash word to an index 0-383
            h = int(hashlib.md5(word.encode('utf-8')).hexdigest()[:8], 16)
            idx = h % 384
            vector[idx] += 1.0
            
        # Normalize
        norm = sum(x*x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]
            
        return vector

class MemoryStore:
    def __init__(self, db_path: str = "~/.codex-mentis/memory.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize Embedder
        if EMBEDDER_AVAILABLE:
            try:
                self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception:
                self.embedder = MockEmbedder()
        else:
            self.embedder = MockEmbedder()

        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    layer TEXT NOT NULL,
                    content TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    messages TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _float_list_to_blob(self, floats: List[float]) -> bytes:
        return struct.pack(f"{len(floats)}f", *floats)

    def _blob_to_float_list(self, blob: bytes) -> List[float]:
        n = len(blob) // 4
        return list(struct.unpack(f"{n}f", blob))

    def get_embedding(self, text: str) -> List[float]:
        # Encode text as embedding vector
        if isinstance(self.embedder, MockEmbedder):
            return self.embedder.encode(text)
        else:
            # sentence-transformers encode returns numpy array or list
            vector = self.embedder.encode(text)
            if hasattr(vector, "tolist"):
                return vector.tolist()
            return list(vector)

    def save(
        self, 
        layer: str, 
        content: str, 
        topic: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Saves a memory unit into SQLite.
        """
        vector = self.get_embedding(content)
        embedding_blob = self._float_list_to_blob(vector)
        metadata_json = json.dumps(metadata or {})
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memories (layer, content, topic, embedding, metadata) VALUES (?, ?, ?, ?, ?)",
                (layer, content, topic, embedding_blob, metadata_json)
            )
            conn.commit()
            return cursor.lastrowid

    def retrieve(
        self, 
        query: str, 
        layer: Optional[str] = None, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top_k relevant memories matching query (semantic search).
        """
        query_vector = self.get_embedding(query)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if layer:
                cursor.execute("SELECT id, layer, content, topic, embedding, timestamp, metadata FROM memories WHERE layer = ?", (layer,))
            else:
                cursor.execute("SELECT id, layer, content, topic, embedding, timestamp, metadata FROM memories")
            
            rows = cursor.fetchall()

        results = []
        for row in rows:
            m_id, m_layer, content, topic, emb_blob, timestamp, metadata_str = row
            m_vector = self._blob_to_float_list(emb_blob)
            
            # Compute cosine similarity
            dot_product = sum(q * m for q, m in zip(query_vector, m_vector))
            q_norm = sum(q*q for q in query_vector) ** 0.5
            m_norm = sum(m*m for m in m_vector) ** 0.5
            
            similarity = dot_product / (q_norm * m_norm) if (q_norm * m_norm) > 0 else 0.0
            
            results.append({
                "id": m_id,
                "layer": m_layer,
                "content": content,
                "topic": topic,
                "timestamp": timestamp,
                "metadata": json.loads(metadata_str or "{}"),
                "score": similarity
            })

        # Sort by similarity score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def save_conversation(self, conversation_id: str, topic: str, messages: List[Dict[str, str]]):
        messages_json = json.dumps(messages)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO conversations (id, topic, messages) VALUES (?, ?, ?)",
                (conversation_id, topic, messages_json)
            )
            conn.commit()

    def get_conversation(self, conversation_id: str) -> Optional[List[Dict[str, str]]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT messages FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None

    def get_topic_history(self, topic: str) -> List[Dict[str, Any]]:
        """
        Retrieves all conversations and memories related to a specific topic.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, layer, content, timestamp FROM memories WHERE topic = ?", (topic,))
            rows = cursor.fetchall()
            
        return [
            {"id": row[0], "layer": row[1], "content": row[2], "timestamp": row[3]}
            for row in rows
        ]

    def get_review_queue(self) -> List[Dict[str, Any]]:
        """
        Returns all memories that need review, checking metadata for spaced repetition attributes.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, layer, content, topic, metadata FROM memories")
            rows = cursor.fetchall()

        now = datetime.datetime.now().date()
        queue = []
        for row in rows:
            m_id, layer, content, topic, meta_str = row
            meta = json.loads(meta_str or "{}")
            
            # Check if has next_review date in metadata
            next_review_str = meta.get("next_review")
            if next_review_str:
                try:
                    next_review = datetime.datetime.strptime(next_review_str, "%Y-%m-%d").date()
                    if next_review <= now:
                        queue.append({
                            "id": m_id,
                            "layer": layer,
                            "content": content,
                            "topic": topic,
                            "metadata": meta
                        })
                except ValueError:
                    pass
        return queue
