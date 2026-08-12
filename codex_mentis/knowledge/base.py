"""Knowledge base manager — ingests, stores, and retrieves documents for RAG."""
import os
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from codex_mentis.core.config import CONFIG_DIR


class KnowledgeBase:
    """Manages the document knowledge base with semantic search."""

    def __init__(self, db_path: Optional[str] = None, embedding_db_path: Optional[str] = None):
        self.db_path = db_path or str(CONFIG_DIR / "knowledge.db")
        self.embedding_db_path = embedding_db_path
        self._ensure_db()

    def create(self, subject: str, description: str = ""):
        """Create a collection/subject in the database."""
        pass

    def _ensure_db(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                subject TEXT DEFAULT 'general',
                ingested_at TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedding BLOB,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
            CREATE INDEX IF NOT EXISTS idx_docs_subject ON documents(subject);
        """)
        conn.close()

    def add_document(self, path: str, title: str, subject: str = "general",
                     chunks: Optional[List[Dict[str, Any]]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> int:
        """Add a document and its chunks to the knowledge base."""
        if subject == "general" and title != "general":
            subject = title
        from codex_mentis.knowledge.ingester import DocumentIngester
        from codex_mentis.knowledge.chunker import SmartChunker

        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()

        # Extract text if no chunks provided
        if chunks is None:
            ingester = DocumentIngester()
            text = ingester.extract_text(path)
            chunker = SmartChunker()
            chunks = chunker.chunk_text(text, source=path)

        # Insert document
        conn.execute(
            "INSERT OR REPLACE INTO documents (path, title, subject, ingested_at, chunk_count, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (path, title, subject, now, len(chunks), json.dumps(metadata or {}))
        )
        doc_id = conn.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()[0]

        # Insert chunks
        for i, chunk in enumerate(chunks):
            conn.execute(
                "INSERT INTO chunks (doc_id, chunk_index, text, metadata) VALUES (?, ?, ?, ?)",
                (doc_id, i, chunk.get("text", ""), json.dumps(chunk.get("metadata", {})))
            )

        conn.commit()
        conn.close()
        return doc_id

    def search(self, query: str, limit: int = 5, subject: Optional[str] = None, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search the knowledge base using text matching (upgradeable to vector search)."""
        if top_k is not None:
            limit = top_k
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        if subject:
            rows = conn.execute("""
                SELECT c.text, c.metadata, d.title, d.path, d.subject
                FROM chunks c JOIN documents d ON c.doc_id = d.id
                WHERE d.subject = ? AND c.text LIKE ?
                ORDER BY c.id DESC LIMIT ?
            """, (subject, f"%{query}%", limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT c.text, c.metadata, d.title, d.path, d.subject
                FROM chunks c JOIN documents d ON c.doc_id = d.id
                WHERE c.text LIKE ?
                ORDER BY c.id DESC LIMIT ?
            """, (f"%{query}%", limit)).fetchall()

        conn.close()
        return [
            {
                "content": row["text"],
                "text": row["text"],
                "score": 1.0,
                "source": row["title"],
                "path": row["path"],
                "subject": row["subject"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
            }
            for row in rows
        ]

    def list_documents(self, subject: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all documents in the knowledge base."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        if subject:
            rows = conn.execute(
                "SELECT * FROM documents WHERE subject = ? ORDER BY ingested_at DESC", (subject,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM documents ORDER BY ingested_at DESC").fetchall()

        conn.close()
        return [dict(row) for row in rows]

    def delete_document(self, path: str) -> bool:
        """Remove a document and its chunks."""
        conn = sqlite3.connect(self.db_path)
        doc = conn.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()
        if not doc:
            conn.close()
            return False
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc[0],))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc[0],))
        conn.commit()
        conn.close()
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        conn = sqlite3.connect(self.db_path)
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        subjects = conn.execute(
            "SELECT subject, COUNT(*) as cnt FROM documents GROUP BY subject ORDER BY cnt DESC"
        ).fetchall()
        conn.close()
        return {
            "documents": doc_count,
            "chunks": chunk_count,
            "subjects": {row[0]: row[1] for row in subjects}
        }

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks — alias for search with compatibility."""
        return self.search(query, limit=top_k)
