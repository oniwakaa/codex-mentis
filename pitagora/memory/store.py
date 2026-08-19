import json
import os
import sqlite3
import struct
from datetime import datetime
from typing import Any

from pitagora.core.constants import MEMORY_DB
from pitagora.core.models import MemoryEntry

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
            norm = sum(x * x for x in dense) ** 0.5
            if norm > 0:
                dense = [x / norm for x in dense]
            return list(dense)
        else:
            # list of strings
            sparse_matrix = self.vectorizer.transform(text)
            dense = sparse_matrix.toarray()
            results = []
            for row in dense:
                norm = sum(x * x for x in row) ** 0.5
                if norm > 0:
                    row = [x / norm for x in row]
                results.append(list(row))
            return results


class MockEmbedder:
    def encode(self, text: str) -> list[float]:
        import hashlib
        import re

        words = re.findall(r"\w+", text.lower())
        vector = [0.0] * 384

        if not words:
            vector[0] = 1.0
            return vector

        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest()[:8], 16)
            idx = h % 384
            vector[idx] += 1.0

        # Normalize
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(x * y for x, y in zip(v1, v2, strict=False))
    norm_v1 = sum(x * x for x in v1) ** 0.5
    norm_v2 = sum(x * x for x in v2) ** 0.5
    if norm_v1 * norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)


class MemoryStore:
    def __init__(self, db_path: str = str(MEMORY_DB)):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        # Initialize Embedder
        self.embedder = None
        if EMBEDDER_AVAILABLE:
            try:
                self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                pass

        if self.embedder is None:
            try:
                self.embedder = TfidfFallbackEmbedder()
            except Exception:
                self.embedder = MockEmbedder()

        self._init_db()

    def _db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            isolation_level="IMMEDIATE",
        )
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def _init_db(self):
        with self._db_connection() as conn:
            cursor = conn.cursor()
            # Table: memory_entries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    layer TEXT NOT NULL,
                    content TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    embedding BLOB,
                    timestamp TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_layer ON memory_entries (layer)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_topic ON memory_entries (topic)")
            # Table: conversations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    topic TEXT,
                    messages TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Table: learner_profile
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learner_profile (
                    key TEXT PRIMARY KEY,
                    category TEXT NOT NULL DEFAULT 'preference',
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Table: misconceptions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS misconceptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    concept TEXT NOT NULL,
                    misconception TEXT NOT NULL,
                    resolution TEXT,
                    resolved INTEGER DEFAULT 0,
                    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _float_list_to_blob(self, floats: list[float]) -> bytes:
        return struct.pack(f"{len(floats)}f", *floats)

    def _blob_to_float_list(self, blob: bytes) -> list[float]:
        if not blob:
            return []
        n = len(blob) // 4
        return list(struct.unpack(f"{n}f", blob))

    def get_embedding(self, text: str) -> list[float]:
        vector = self.embedder.encode(text)
        if hasattr(vector, "tolist"):
            return vector.tolist()
        return list(vector)

    # --- Full CRUD operations ---
    def create_memory_entry(self, entry: MemoryEntry) -> int:
        vector = entry.embedding
        if not vector:
            vector = self.get_embedding(entry.content)
        embedding_blob = self._float_list_to_blob(vector)
        metadata_str = json.dumps(entry.metadata or {})
        timestamp_str = (
            entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if entry.timestamp
            else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        with self._db_connection() as conn:
            cursor = conn.cursor()
            # Try upsert first to preserve created_at on conflict; if entry.id is None, it will create new row
            cursor.execute(
                """INSERT INTO memory_entries (id, layer, content, topic, embedding, timestamp, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    layer = excluded.layer,
                    content = excluded.content,
                    topic = excluded.topic,
                    embedding = excluded.embedding,
                    timestamp = excluded.timestamp,
                    metadata = excluded.metadata,
                    created_at = memory_entries.created_at""",
                (
                    entry.id,
                    entry.layer,
                    entry.content,
                    entry.topic,
                    embedding_blob,
                    timestamp_str,
                    metadata_str,
                ),
            )
            conn.commit()
            # If no id was provided (entry.id is None), lastrowid is the new id
            if entry.id is None:
                return int(cursor.lastrowid) if cursor.lastrowid else 0
            # If id was provided, return the existing/updated id
            return int(entry.id)
        # Note: in normal operation this path is not reached; kept for safety
        return int(entry.id) if entry.id is not None else 0

    def get_memory_entry(self, entry_id: int) -> MemoryEntry | None:
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, layer, content, topic, embedding, timestamp, metadata, created_at FROM memory_entries WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return MemoryEntry(
                id=row[0],
                layer=row[1],
                content=row[2],
                topic=row[3],
                embedding=self._blob_to_float_list(row[4]) if row[4] else [],
                timestamp=(
                    datetime.strptime(row[5], "%Y-%m-%d %H:%M:%S") if row[5] else datetime.now()
                ),
                metadata=json.loads(row[6] or "{}"),
            )

    def update_memory_entry(self, entry_id: int, entry: MemoryEntry) -> bool:
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM memory_entries WHERE id = ?", (entry_id,))
            if not cursor.fetchone():
                return False
            row_updates: dict[str, Any] = {}
            if entry.layer is not None:
                row_updates["layer"] = entry.layer
            if entry.content is not None:
                row_updates["content"] = entry.content
                vector = entry.embedding or self.get_embedding(entry.content)
                row_updates["embedding"] = self._float_list_to_blob(vector)
            if entry.topic is not None:
                row_updates["topic"] = entry.topic
            if entry.metadata is not None:
                row_updates["metadata"] = json.dumps(entry.metadata)
            if entry.timestamp is not None:
                row_updates["timestamp"] = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            # Preserve created_at: do not update it on upsert/update
            if row_updates:
                set_clause = ", ".join(f"{k} = ?" for k in row_updates)
                values = list(row_updates.values()) + [entry_id]
                cursor.execute(f"UPDATE memory_entries SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def delete_memory_entry(self, entry_id: int) -> bool:
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_memories(
        self, layer: str | None = None, topic: str | None = None
    ) -> list[MemoryEntry]:
        with self._db_connection() as conn:
            cursor = conn.cursor()
            params: list[Any] = []
            where_parts: list[str] = []
            if layer is not None:
                where_parts.append("layer = ?")
                params.append(layer)
            if topic is not None:
                where_parts.append("topic = ?")
                params.append(topic)
            sql = "SELECT id, layer, content, topic, embedding, timestamp, metadata, created_at FROM memory_entries"
            if where_parts:
                sql += " WHERE " + " AND ".join(where_parts)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append(
                MemoryEntry(
                    id=row[0],
                    layer=row[1],
                    content=row[2],
                    topic=row[3],
                    embedding=self._blob_to_float_list(row[4]) if row[4] else [],
                    timestamp=(
                        datetime.strptime(row[5], "%Y-%m-%d %H:%M:%S") if row[5] else datetime.now()
                    ),
                    metadata=json.loads(row[6] or "{}"),
                )
            )
        return results

    # --- Legacy/compatibility CRUD interface ---
    def save(
        self,
        layer: str,
        content: str,
        topic: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        entry = MemoryEntry(
            layer=layer,
            content=content,
            topic=topic,
            metadata=metadata or {},
        )
        return self.create_memory_entry(entry)

    # Read-only: retrieve without creating graph entities
    def retrieve(
        self, query: str, layer: str | None = None, top_k: int = 5
    ) -> list[dict[str, Any]]:
        # Read-only: must not create graph entities or modify DB
        query_vector = self.get_embedding(query)
        with self._db_connection() as conn:
            cursor = conn.cursor()
            if layer is not None:
                cursor.execute(
                    "SELECT id, layer, content, topic, embedding, timestamp, metadata FROM memory_entries WHERE layer = ?",
                    (layer,),
                )
            else:
                cursor.execute(
                    "SELECT id, layer, content, topic, embedding, timestamp, metadata FROM memory_entries"
                )
            rows = cursor.fetchall()
        results = []
        for row in rows:
            # Embedding is at index 3 in SELECT order above (id=0, layer=1, content=2, topic=3, embedding=4...)
            # Wait: SELECT order is: id, layer, content, topic, embedding, timestamp, metadata
            # So index mapping: 0=id, 1=layer, 2=content, 3=topic, 4=embedding, 5=timestamp, 6=metadata
            m_vector = self._blob_to_float_list(row[4]) if row[4] else []
            similarity = cosine_similarity(query_vector, m_vector)
            results.append(
                {
                    "id": row[0],
                    "layer": row[1],
                    "content": row[2],
                    "topic": row[3],
                    "timestamp": row[5],
                    "metadata": json.loads(row[6] or "{}"),
                    "score": similarity,
                }
            )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def save_conversation(self, conversation_id: str, topic: str, messages: list[dict[str, str]]):
        with self._db_connection() as conn:
            cursor = conn.cursor()
            messages_json = json.dumps(messages)
            cursor.execute(
                "INSERT INTO conversations (id, topic, messages, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(id) DO UPDATE SET messages = excluded.messages, topic = excluded.topic, created_at = conversations.created_at",
                (conversation_id, topic, messages_json),
            )
            conn.commit()

    def get_conversation(self, conversation_id: str) -> list[dict[str, str]] | None:
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT messages FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return json.loads(row[0])

    def get_topic_history(self, topic: str) -> list[dict[str, Any]]:
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, layer, content, timestamp FROM memory_entries WHERE topic = ?",
                (topic,),
            )
            rows = cursor.fetchall()
        return [
            {"id": row[0], "layer": row[1], "content": row[2], "timestamp": row[3]} for row in rows
        ]

    def get_review_queue(self) -> list[dict[str, Any]]:
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, layer, content, topic, timestamp, metadata FROM memory_entries"
            )
            rows = cursor.fetchall()
        now = datetime.now().date()
        queue = []
        for row in rows:
            meta = json.loads(row[5] or "{}")
            next_review_str = meta.get("next_review")
            if next_review_str:
                try:
                    next_review = datetime.strptime(next_review_str, "%Y-%m-%d").date()
                    if next_review <= now:
                        queue.append(
                            {
                                "id": row[0],
                                "layer": row[1],
                                "content": row[2],
                                "topic": row[3],
                                "metadata": meta,
                            }
                        )
                except ValueError:
                    pass
        return queue

    # --- Layer promotion and synthesis ---
    def promote_l1_to_l2(self, conversation_id: str, provider: Any | None = None) -> int | None:
        messages = self.get_conversation(conversation_id)
        if not messages:
            return None

        topic = "General"
        with self._db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT topic FROM conversations WHERE id = ?", (conversation_id,))
                conv_row = cursor.fetchone()
                if conv_row:
                    topic = conv_row[0]
            except Exception:
                pass

        chat_history = "\n".join(
            [f"{msg.get('role', '?').upper()}: {msg.get('content', '')}" for msg in messages]
        )
        prompt = (
            f"Below is a chat session transcript on the topic of '{topic}'. "
            f"Summarize the key mathematical formulas, physical concepts, and reasoning paths. "
            f"Keep it concise but ensure formulas are preserved in LaTeX:\n\n" + chat_history
        )

        summary = ""
        if provider:
            try:
                resp = provider.complete([{"role": "user", "content": prompt}])
                summary = resp.get("content", "")
            except Exception as e:
                summary = f"Error generating summary: {e}"

        if not summary:
            summary = f"Summary of session about {topic} containing {len(messages)} messages."

        return self.save(layer="L2", content=summary, topic=topic)

    def synthesize_l2_to_l3(self, topics: list[str], provider: Any | None = None) -> int | None:
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
                synthesis = f"Error generating synthesis: {e}"

        if not synthesis:
            synthesis = (
                f"Synthesis of topics: {', '.join(topics)}. Connections identified between fields."
            )

        return self.save(layer="L3", content=synthesis, topic=",".join(topics))

    # --- Backup using SQLite backup API ---
    def backup_database(self, dest_path: str) -> bool:
        try:
            dest_path = os.path.expanduser(dest_path)
            dest_dir = os.path.dirname(dest_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            with sqlite3.connect(self.db_path) as src:
                with sqlite3.connect(dest_path) as dst:
                    src.backup(dst, pages=1, progress=lambda *args: None)
            return True
        except Exception:
            return False

    # --- Export memories ---
    def export_memories(self, dest_path: str) -> bool:
        try:
            dest_path = os.path.expanduser(dest_path)
            dest_dir = os.path.dirname(dest_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            with self._db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, layer, content, topic, embedding, timestamp, metadata, created_at FROM memory_entries"
                )
                rows = cursor.fetchall()
            memories = []
            for row in rows:
                memories.append(
                    {
                        "id": row[0],
                        "layer": row[1],
                        "content": row[2],
                        "topic": row[3],
                        "embedding": self._blob_to_float_list(row[4]) if row[4] else [],
                        "timestamp": row[5],
                        "metadata": json.loads(row[6] or "{}"),
                        "created_at": row[7],
                    }
                )
            with open(dest_path, "w", encoding="utf-8") as f:
                json.dump(memories, f, indent=2, default=str)
            return True
        except Exception:
            return False

    # --- Validated transactional import counterpart ---
    def import_memories(self, source_path: str) -> bool:
        try:
            source_path = os.path.expanduser(source_path)
            with open(source_path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return False
            with self._db_connection() as conn:
                cursor = conn.cursor()
                # Use explicit transaction for rollback on corruption
                cursor.execute("BEGIN IMMEDIATE")
                try:
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        # Validate required fields
                        layer = item.get("layer")
                        content = item.get("content")
                        topic = item.get("topic")
                        if layer is None or content is None or topic is None:
                            # Skip invalid rows rather than corrupting DB
                            continue
                        embedding_blob = None
                        emb = item.get("embedding")
                        if isinstance(emb, list) and emb:
                            embedding_blob = self._float_list_to_blob(emb)
                        metadata_str = json.dumps(item.get("metadata", {}) or {})
                        timestamp_str = item.get("timestamp")
                        if not timestamp_str:
                            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        created_at_str = item.get("created_at") or timestamp_str
                        # Upsert: preserve created_at on conflict
                        cursor.execute(
                            "INSERT INTO memory_entries (id, layer, content, topic, embedding, timestamp, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET layer = excluded.layer, content = excluded.content, topic = excluded.topic, embedding = excluded.embedding, timestamp = excluded.timestamp, metadata = excluded.metadata, created_at = memory_entries.created_at",
                            (
                                item.get("id"),
                                layer,
                                content,
                                topic,
                                embedding_blob,
                                timestamp_str,
                                metadata_str,
                                created_at_str,
                            ),
                        )
                    conn.commit()
                    return True
                except Exception:
                    conn.rollback()
                    return False
        except Exception:
            return False

    # --- Learner Profile & Cross-Session Fact Store ---
    def record_learner_fact(self, key: str, value: Any, category: str = "preference") -> None:
        """Store or update a persistent learner fact (preference, target pace, known background)."""
        val_str = json.dumps(value) if not isinstance(value, str) else value
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO learner_profile (key, category, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    category = excluded.category,
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP""",
                (key, category, val_str),
            )
            conn.commit()

    def get_learner_facts(self, category: str | None = None) -> dict[str, Any]:
        """Retrieve stored learner facts."""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    "SELECT key, value FROM learner_profile WHERE category = ?", (category,)
                )
            else:
                cursor.execute("SELECT key, value FROM learner_profile")
            rows = cursor.fetchall()
        facts = {}
        for k, v in rows:
            try:
                facts[k] = json.loads(v)
            except Exception:
                facts[k] = v
        return facts

    # --- Misconceptions Tracking ---
    def record_misconception(
        self, topic: str, concept: str, misconception: str, resolution: str | None = None
    ) -> int:
        """Record a misconception encountered by the user for targeted review."""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO misconceptions (topic, concept, misconception, resolution, resolved, recorded_at)
                VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)""",
                (topic, concept, misconception, resolution),
            )
            conn.commit()
            return int(cursor.lastrowid) if cursor.lastrowid else 0

    def resolve_misconception(self, misconception_id: int, resolution: str | None = None) -> bool:
        """Mark a misconception as resolved."""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            if resolution:
                cursor.execute(
                    "UPDATE misconceptions SET resolved = 1, resolution = ? WHERE id = ?",
                    (resolution, misconception_id),
                )
            else:
                cursor.execute(
                    "UPDATE misconceptions SET resolved = 1 WHERE id = ?", (misconception_id,)
                )
            conn.commit()
            return cursor.rowcount > 0

    def get_misconceptions(
        self, topic: str | None = None, concept: str | None = None, unresolved_only: bool = True
    ) -> list[dict[str, Any]]:
        """Retrieve tracked misconceptions."""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, topic, concept, misconception, resolution, resolved, recorded_at FROM misconceptions"
            params: list[Any] = []
            where = []
            if topic:
                where.append("topic = ?")
                params.append(topic)
            if concept:
                where.append("concept = ?")
                params.append(concept)
            if unresolved_only:
                where.append("resolved = 0")
            if where:
                query += " WHERE " + " AND ".join(where)
            query += " ORDER BY recorded_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "topic": r[1],
                "concept": r[2],
                "misconception": r[3],
                "resolution": r[4],
                "resolved": bool(r[5]),
                "recorded_at": r[6],
            }
            for r in rows
        ]

    def get_learner_snapshot(self, topic: str | None = None) -> str:
        """Generate a dense, high-signal summary of learner state across sessions."""
        facts = self.get_learner_facts()
        misconceptions = self.get_misconceptions(topic=topic, unresolved_only=True)
        parts = []
        if facts:
            pref_strs = [f"{k}={v}" for k, v in facts.items() if k not in ("name", "id")]
            if pref_strs:
                parts.append(f"Learner preferences: {', '.join(pref_strs[:4])}")
        if misconceptions:
            misc_strs = [f"'{m['concept']}': {m['misconception']}" for m in misconceptions[:2]]
            parts.append(f"Known hurdles to reinforce: {'; '.join(misc_strs)}")
        return "\n".join(parts)

