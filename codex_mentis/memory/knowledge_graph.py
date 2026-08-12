import datetime
import json
import logging
import os
import sqlite3
import struct
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from codex_mentis.agents.base import BaseAgent

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False

class MockEmbedder:
    def encode(self, text: str) -> List[float]:
        """
        Feature-hashing bag-of-words embedder as a fallback.
        Provides a real keyword-overlap vector space model.
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

class EntityNode(BaseModel):
    id: str
    name: str
    entity_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    is_deleted: int = 0

class Relationship(BaseModel):
    source_id: str
    target_id: str
    rel_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0
    created_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    is_deleted: int = 0

class KnowledgeGraph:
    def __init__(self, db_path: str = "~/.codex-mentis/knowledge_graph.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    properties TEXT,
                    embedding BLOB,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_deleted INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    rel_type TEXT NOT NULL,
                    properties TEXT,
                    weight REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_deleted INTEGER DEFAULT 0,
                    PRIMARY KEY (source_id, target_id, rel_type),
                    FOREIGN KEY (source_id) REFERENCES entities(id),
                    FOREIGN KEY (target_id) REFERENCES entities(id)
                )
            """)
            conn.commit()

    def _float_list_to_blob(self, floats: List[float]) -> bytes:
        return struct.pack(f"{len(floats)}f", *floats)

    def _blob_to_float_list(self, blob: bytes) -> List[float]:
        if not blob:
            return []
        n = len(blob) // 4
        return list(struct.unpack(f"{n}f", blob))

    def get_embedding(self, text: str) -> List[float]:
        if isinstance(self.embedder, MockEmbedder):
            return self.embedder.encode(text)
        else:
            vector = self.embedder.encode(text)
            if hasattr(vector, "tolist"):
                return vector.tolist()
            return list(vector)

    def _resolve_entity_id(self, name_or_id: str) -> str:
        # Match case-insensitive or exact
        slug = name_or_id.strip().lower().replace(" ", "_")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM entities WHERE (id = ? OR name = ?) AND is_deleted = 0", (slug, name_or_id))
            row = cursor.fetchone()
            if row:
                return row[0]
            
            cursor.execute("SELECT id FROM entities WHERE id = ?", (slug,))
            row = cursor.fetchone()
            if row:
                return slug
                
        # Automatically insert if not found
        return self.add_entity(name_or_id, "Concept")

    def add_entity(self, name: str, entity_type: str, properties: Optional[Dict[str, Any]] = None) -> str:
        entity_id = name.strip().lower().replace(" ", "_")
        properties = properties or {}
        now = datetime.datetime.now().isoformat()
        
        # Embed based on name and entity description properties
        desc = f"{name} {entity_type} " + " ".join(str(v) for v in properties.values())
        embedding_vector = self.get_embedding(desc)
        embedding_blob = self._float_list_to_blob(embedding_vector)
        properties_json = json.dumps(properties)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT properties, is_deleted FROM entities WHERE id = ?", (entity_id,))
            row = cursor.fetchone()
            
            if row:
                existing_properties = json.loads(row[0] or "{}")
                merged_properties = {**existing_properties, **properties}
                merged_properties_json = json.dumps(merged_properties)
                cursor.execute(
                    "UPDATE entities SET properties = ?, embedding = ?, updated_at = ?, is_deleted = 0 WHERE id = ?",
                    (merged_properties_json, embedding_blob, now, entity_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO entities (id, name, entity_type, properties, embedding, created_at, updated_at, is_deleted) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                    (entity_id, name, entity_type, properties_json, embedding_blob, now, now)
                )
            conn.commit()
            
        return entity_id

    def add_relationship(self, source: str, target: str, rel_type: str, properties: Optional[Dict[str, Any]] = None, weight: float = 1.0):
        source_id = self._resolve_entity_id(source)
        target_id = self._resolve_entity_id(target)
        properties = properties or {}
        now = datetime.datetime.now().isoformat()
        properties_json = json.dumps(properties)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT properties, weight FROM relationships WHERE source_id = ? AND target_id = ? AND rel_type = ?",
                (source_id, target_id, rel_type)
            )
            row = cursor.fetchone()
            if row:
                existing_properties = json.loads(row[0] or "{}")
                merged_properties = {**existing_properties, **properties}
                merged_properties_json = json.dumps(merged_properties)
                cursor.execute(
                    "UPDATE relationships SET properties = ?, weight = ?, updated_at = ?, is_deleted = 0 WHERE source_id = ? AND target_id = ? AND rel_type = ?",
                    (merged_properties_json, weight, now, source_id, target_id, rel_type)
                )
            else:
                cursor.execute(
                    "INSERT INTO relationships (source_id, target_id, rel_type, properties, weight, created_at, updated_at, is_deleted) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                    (source_id, target_id, rel_type, properties_json, weight, now, now)
                )
            conn.commit()

    def find_entity(self, name_or_id: str) -> Optional[EntityNode]:
        slug = name_or_id.strip().lower().replace(" ", "_")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, entity_type, properties, embedding, created_at, updated_at FROM entities WHERE (id = ? OR name = ? OR id = ?) AND is_deleted = 0",
                (name_or_id, name_or_id, slug)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            e_id, name, e_type, properties_json, emb_blob, created_at, updated_at = row
            embedding = self._blob_to_float_list(emb_blob) if emb_blob else None
            return EntityNode(
                id=e_id,
                name=name,
                entity_type=e_type,
                properties=json.loads(properties_json or "{}"),
                embedding=embedding,
                created_at=created_at,
                updated_at=updated_at
            )

    def find_related(self, entity_id: str, rel_type: Optional[str] = None, depth: int = 2) -> List[Tuple[EntityNode, Relationship, int]]:
        resolved_id = self._resolve_entity_id(entity_id)
        visited = {resolved_id}
        queue = [(resolved_id, 1)]
        results = []
        
        while queue:
            curr_id, curr_depth = queue.pop(0)
            if curr_depth > depth:
                continue
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if rel_type:
                    cursor.execute(
                        "SELECT source_id, target_id, rel_type, properties, weight, created_at, updated_at FROM relationships "
                        "WHERE (source_id = ? OR target_id = ?) AND rel_type = ? AND is_deleted = 0",
                        (curr_id, curr_id, rel_type)
                    )
                else:
                    cursor.execute(
                        "SELECT source_id, target_id, rel_type, properties, weight, created_at, updated_at FROM relationships "
                        "WHERE (source_id = ? OR target_id = ?) AND is_deleted = 0",
                        (curr_id, curr_id)
                    )
                rows = cursor.fetchall()
                
            for row in rows:
                src, tgt, r_type, r_props_json, weight, c_at, u_at = row
                related_id = tgt if src == curr_id else src
                
                related_entity = self.find_entity(related_id)
                if not related_entity:
                    continue
                
                rel = Relationship(
                    source_id=src,
                    target_id=tgt,
                    rel_type=r_type,
                    properties=json.loads(r_props_json or "{}"),
                    weight=weight,
                    created_at=c_at,
                    updated_at=u_at
                )
                
                results.append((related_entity, rel, curr_depth))
                
                if related_id not in visited:
                    visited.add(related_id)
                    queue.append((related_id, curr_depth + 1))
                    
        return results

    def semantic_search(self, query: str, limit: int = 5) -> List[EntityNode]:
        query_vector = self.get_embedding(query)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, entity_type, properties, embedding, created_at, updated_at FROM entities WHERE is_deleted = 0")
            rows = cursor.fetchall()
            
        results = []
        for row in rows:
            e_id, name, e_type, properties_json, emb_blob, created_at, updated_at = row
            if not emb_blob:
                continue
            m_vector = self._blob_to_float_list(emb_blob)
            
            # Compute cosine similarity
            dot_product = sum(q * m for q, m in zip(query_vector, m_vector))
            q_norm = sum(q*q for q in query_vector) ** 0.5
            m_norm = sum(m*m for m in m_vector) ** 0.5
            
            similarity = dot_product / (q_norm * m_norm) if (q_norm * m_norm) > 0 else 0.0
            
            results.append((similarity, EntityNode(
                id=e_id,
                name=name,
                entity_type=e_type,
                properties=json.loads(properties_json or "{}"),
                embedding=m_vector,
                created_at=created_at,
                updated_at=updated_at
            )))
            
        results.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in results[:limit]]

    def graph_traversal(self, start_id: str, max_depth: int = 2, rel_types: Optional[List[str]] = None) -> Dict[str, Any]:
        resolved_id = self._resolve_entity_id(start_id)
        start_entity = self.find_entity(resolved_id)
        if not start_entity:
            return {"nodes": [], "relationships": []}
            
        visited_nodes = {resolved_id: start_entity}
        visited_relationships = {}
        
        queue = [(resolved_id, 0)]
        while queue:
            curr_id, curr_depth = queue.pop(0)
            if curr_depth >= max_depth:
                continue
                
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT source_id, target_id, rel_type, properties, weight, created_at, updated_at FROM relationships "
                    "WHERE (source_id = ? OR target_id = ?) AND is_deleted = 0",
                    (curr_id, curr_id)
                )
                rows = cursor.fetchall()
                
            for row in rows:
                src, tgt, r_type, r_props_json, weight, c_at, u_at = row
                if rel_types and r_type not in rel_types:
                    continue
                    
                rel_key = (src, tgt, r_type)
                if rel_key in visited_relationships:
                    continue
                    
                rel = Relationship(
                    source_id=src,
                    target_id=tgt,
                    rel_type=r_type,
                    properties=json.loads(r_props_json or "{}"),
                    weight=weight,
                    created_at=c_at,
                    updated_at=u_at
                )
                visited_relationships[rel_key] = rel
                
                related_id = tgt if src == curr_id else src
                if related_id not in visited_nodes:
                    related_entity = self.find_entity(related_id)
                    if related_entity:
                        visited_nodes[related_id] = related_entity
                        queue.append((related_id, curr_depth + 1))
                        
        return {
            "nodes": list(visited_nodes.values()),
            "relationships": list(visited_relationships.values())
        }

    def merge_entities(self, id1: str, id2: str) -> str:
        e1 = self.find_entity(id1)
        e2 = self.find_entity(id2)
        if not e1 or not e2:
            raise ValueError(f"Entities not found: {id1} or {id2}")
            
        now = datetime.datetime.now().isoformat()
        merged_properties = {**e2.properties, **e1.properties}
        merged_properties_json = json.dumps(merged_properties)
        
        # 1. Fetch relationships to migrate
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT target_id, rel_type, properties, weight FROM relationships WHERE source_id = ? AND is_deleted = 0", (id2,))
            source_rels = cursor.fetchall()
            cursor.execute("SELECT source_id, rel_type, properties, weight FROM relationships WHERE target_id = ? AND is_deleted = 0", (id2,))
            target_rels = cursor.fetchall()
            
        # 2. Add migrated relationships outside of connection transaction to avoid locks
        for tgt, r_type, r_props_json, weight in source_rels:
            if tgt != id1:
                self.add_relationship(id1, tgt, r_type, json.loads(r_props_json or "{}"), weight)
                
        for src, r_type, r_props_json, weight in target_rels:
            if src != id1:
                self.add_relationship(src, id1, r_type, json.loads(r_props_json or "{}"), weight)
                
        # 3. Soft-delete the absorbed node and original relationships, and update merged properties
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE entities SET properties = ?, updated_at = ? WHERE id = ?",
                (merged_properties_json, now, id1)
            )
            cursor.execute("UPDATE entities SET is_deleted = 1, updated_at = ? WHERE id = ?", (now, id2))
            cursor.execute("UPDATE relationships SET is_deleted = 1, updated_at = ? WHERE source_id = ? OR target_id = ?", (now, id2, id2))
            conn.commit()
            
        return id1

    def forget(self, entity_id: str):
        resolved_id = self._resolve_entity_id(entity_id)
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE entities SET is_deleted = 1, updated_at = ? WHERE id = ?", (now, resolved_id))
            cursor.execute("UPDATE relationships SET is_deleted = 1, updated_at = ? WHERE source_id = ? OR target_id = ?", (now, resolved_id, resolved_id))
            conn.commit()

    def get_context_window(self, entity_id: str, max_tokens: int = 1000) -> str:
        resolved_id = self._resolve_entity_id(entity_id)
        entity = self.find_entity(resolved_id)
        if not entity:
            return ""
            
        related = self.find_related(resolved_id, depth=1)
        
        lines = [f"Entity: {entity.name} (Type: {entity.entity_type})"]
        if entity.properties:
            lines.append("Properties:")
            for k, v in entity.properties.items():
                lines.append(f"  - {k}: {v}")
                
        if related:
            lines.append("Relationships:")
            for rel_entity, rel, _ in related:
                if rel.source_id == resolved_id:
                    lines.append(f"  - {entity.name} --[{rel.rel_type} (weight: {rel.weight})]--> {rel_entity.name}")
                else:
                    lines.append(f"  - {rel_entity.name} --[{rel.rel_type} (weight: {rel.weight})]--> {entity.name}")
                    
        context_str = "\n".join(lines)
        char_limit = max_tokens * 4
        if len(context_str) > char_limit:
            context_str = context_str[:char_limit] + "\n... [Context truncated]"
            
        return context_str

    def temporal_query(self, entity_id: str, before: Optional[str] = None, after: Optional[str] = None) -> List[Dict[str, Any]]:
        resolved_id = self._resolve_entity_id(entity_id)
        query_parts = ["(source_id = ? OR target_id = ?) AND is_deleted = 0"]
        params = [resolved_id, resolved_id]
        
        if before:
            query_parts.append("updated_at < ?")
            params.append(before)
        if after:
            query_parts.append("updated_at > ?")
            params.append(after)
            
        sql = "SELECT source_id, target_id, rel_type, properties, weight, updated_at FROM relationships WHERE " + " AND ".join(query_parts)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            
        results = []
        for row in rows:
            src, tgt, r_type, r_props_json, weight, u_at = row
            results.append({
                "type": "relationship",
                "source_id": src,
                "target_id": tgt,
                "relationship_type": r_type,
                "properties": json.loads(r_props_json or "{}"),
                "weight": weight,
                "timestamp": u_at
            })
        return results

    async def remember(self, text: str, agent: BaseAgent) -> Dict[str, Any]:
        """
        Extracts entities and relationships using the LLM in structured format,
        and adds them to this knowledge graph.
        """
        class ExtractedEntity(BaseModel):
            name: str
            type: str
            properties: Dict[str, Any] = Field(default_factory=dict)
            
        class ExtractedRelationship(BaseModel):
            source: str
            target: str
            type: str
            properties: Dict[str, Any] = Field(default_factory=dict)
            weight: float = 1.0
            
        class GraphExtraction(BaseModel):
            entities: List[ExtractedEntity]
            relationships: List[ExtractedRelationship]

        prompt = (
            f"Analyze the following text and extract all important mathematical/physical concepts, "
            f"constants, equations, or agents as entities, along with their properties and relationships. "
            f"Identify relationships like 'prerequisite_of', 'generalizes', 'applies_to', etc.\n\n"
            f"Text:\n\"\"\"\n{text}\n\"\"\""
        )
        
        extracted: GraphExtraction = await agent.athink_structured(prompt, GraphExtraction)
        
        added_entities = []
        for ent in extracted.entities:
            ent_id = self.add_entity(ent.name, ent.type, ent.properties)
            added_entities.append(ent_id)
            
        for rel in extracted.relationships:
            self.add_relationship(rel.source, rel.target, rel.type, rel.properties, rel.weight)
            
        return {
            "entities_extracted": len(extracted.entities),
            "relationships_extracted": len(extracted.relationships),
            "entity_ids": added_entities
        }

    def recall(self, query: str) -> Dict[str, Any]:
        """
        Hybrid routing: query is used for semantic search, and matching entity
        subgraphs are fetched via graph traversal.
        """
        entities = self.semantic_search(query, limit=3)
        if not entities:
            return {"nodes": [], "relationships": [], "source": "empty"}
            
        primary_entity = entities[0]
        subgraph = self.graph_traversal(primary_entity.id, max_depth=2)
        
        # Ensure all semantic search matches are present in nodes list
        existing_ids = {node.id for node in subgraph["nodes"]}
        for ent in entities:
            if ent.id not in existing_ids:
                subgraph["nodes"].append(ent)
                
        return {
            "nodes": subgraph["nodes"],
            "relationships": subgraph["relationships"],
            "primary_entity": primary_entity.name,
            "source": "hybrid_search"
        }

    def improve(self, entity_id: str, feedback: str, score_delta: float) -> None:
        """
        Adjust relationship weights connected to the entity based on feedback.
        """
        resolved_id = self._resolve_entity_id(entity_id)
        now = datetime.datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT source_id, target_id, rel_type, weight, properties FROM relationships "
                "WHERE (source_id = ? OR target_id = ?) AND is_deleted = 0",
                (resolved_id, resolved_id)
            )
            rows = cursor.fetchall()
            
            for row in rows:
                src, tgt, r_type, weight, props_json = row
                new_weight = max(0.0, min(2.0, weight + score_delta))
                
                props = json.loads(props_json or "{}")
                props["last_feedback"] = feedback
                props["feedback_history"] = props.get("feedback_history", []) + [feedback]
                
                cursor.execute(
                    "UPDATE relationships SET weight = ?, properties = ?, updated_at = ? "
                    "WHERE source_id = ? AND target_id = ? AND rel_type = ?",
                    (new_weight, json.dumps(props), now, src, tgt, r_type)
                )
            conn.commit()
