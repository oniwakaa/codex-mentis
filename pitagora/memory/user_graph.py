"""User knowledge graph — tracks relationships between users, topics, and concepts."""
import os
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class GraphNode:
    id: str
    node_type: str  # user, topic, concept, document, session
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class GraphEdge:
    source: str
    target: str
    edge_type: str  # studied, mastered, struggling_with, reviewed, interested_in, prerequisite_of
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


class UserGraph:
    """Tracks the relationship between users and their knowledge."""

    def __init__(self, db_path: Optional[str] = None):
        from pitagora.core.config import CONFIG_DIR
        self.db_path = db_path or str(CONFIG_DIR / "user_graph.db")
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                properties TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                UNIQUE(source, target, edge_type)
            );
            CREATE INDEX IF NOT EXISTS idx_edges_source ON graph_edges(source);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON graph_edges(target);
            CREATE INDEX IF NOT EXISTS idx_edges_type ON graph_edges(edge_type);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON graph_nodes(node_type);
        """)
        conn.close()

    def add_node(self, node_id: str, node_type: str, properties: Optional[Dict] = None) -> str:
        """Add a node to the graph."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO graph_nodes (id, node_type, properties, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (node_id, node_type, json.dumps(properties or {}), now, now)
        )
        conn.commit()
        conn.close()
        return node_id

    def add_edge(self, source: str, target: str, edge_type: str,
                 weight: float = 1.0, properties: Optional[Dict] = None) -> None:
        """Add an edge between two nodes."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO graph_edges (source, target, edge_type, weight, properties, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, target, edge_type, weight, json.dumps(properties or {}), now)
        )
        conn.commit()
        conn.close()

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT * FROM graph_nodes WHERE id = ?", (node_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return GraphNode(id=row[0], node_type=row[1], properties=json.loads(row[2]),
                        created_at=row[3], updated_at=row[4])

    def get_neighbors(self, node_id: str, edge_types: Optional[List[str]] = None,
                      direction: str = "outgoing") -> List[Tuple[GraphNode, GraphEdge]]:
        """Get neighboring nodes connected by edges."""
        conn = sqlite3.connect(self.db_path)
        
        if direction == "outgoing":
            query = "SELECT * FROM graph_edges WHERE source = ?"
            params = [node_id]
        elif direction == "incoming":
            query = "SELECT * FROM graph_edges WHERE target = ?"
            params = [node_id]
        else:  # both
            query = "SELECT * FROM graph_edges WHERE source = ? OR target = ?"
            params = [node_id, node_id]

        if edge_types:
            placeholders = ",".join("?" * len(edge_types))
            query += f" AND edge_type IN ({placeholders})"
            params.extend(edge_types)

        edges = conn.execute(query, params).fetchall()
        results = []
        
        for edge_row in edges:
            edge = GraphEdge(source=edge_row[1], target=edge_row[2], edge_type=edge_row[3],
                           weight=edge_row[4], properties=json.loads(edge_row[5]), created_at=edge_row[6])
            neighbor_id = edge.target if edge.source == node_id else edge.source
            node_row = conn.execute("SELECT * FROM graph_nodes WHERE id = ?", (neighbor_id,)).fetchone()
            if node_row:
                node = GraphNode(id=node_row[0], node_type=node_row[1],
                               properties=json.loads(node_row[2]), created_at=node_row[3], updated_at=node_row[4])
                results.append((node, edge))

        conn.close()
        return results

    def traverse(self, start_id: str, max_depth: int = 2,
                 edge_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """BFS traversal from start node, returns adjacency list."""
        visited: Set[str] = set()
        adjacency: Dict[str, List[Dict]] = {}
        queue = [(start_id, 0)]

        while queue:
            node_id, depth = queue.pop(0)
            if node_id in visited or depth > max_depth:
                continue
            visited.add(node_id)

            neighbors = self.get_neighbors(node_id, edge_types=edge_filter)
            adjacency[node_id] = []
            for neighbor_node, edge in neighbors:
                adjacency[node_id].append({
                    "node": neighbor_node.id,
                    "type": neighbor_node.node_type,
                    "edge": edge.edge_type,
                    "weight": edge.weight,
                })
                if depth < max_depth:
                    queue.append((neighbor_node.id, depth + 1))

        return adjacency

    def shortest_path(self, from_id: str, to_id: str, max_depth: int = 5) -> Optional[List[str]]:
        """Find shortest path between two nodes using BFS."""
        from collections import deque
        visited: Set[str] = set()
        queue: deque = deque([(from_id, [from_id])])

        while queue:
            current, path = queue.popleft()
            if current == to_id:
                return path
            if current in visited or len(path) > max_depth:
                continue
            visited.add(current)

            neighbors = self.get_neighbors(current)
            for neighbor_node, edge in neighbors:
                if neighbor_node.id not in visited:
                    queue.append((neighbor_node.id, path + [neighbor_node.id]))

        return None

    def recommend_next(self, user_id: str) -> List[Dict[str, Any]]:
        """Recommend topics to study next based on prerequisites and mastery."""
        conn = sqlite3.connect(self.db_path)
        
        # Get topics the user has studied
        studied = set()
        rows = conn.execute(
            "SELECT target FROM graph_edges WHERE source = ? AND edge_type IN ('studied', 'mastered')",
            (user_id,)
        ).fetchall()
        for row in rows:
            studied.add(row[0])

        # Get all topics with prerequisites
        recommendations = []
        topics = conn.execute("SELECT id, properties FROM graph_nodes WHERE node_type = 'topic'").fetchall()
        
        for topic_id, props_json in topics:
            if topic_id in studied:
                continue
            
            # Check if prerequisites are met
            prereqs = conn.execute(
                "SELECT source FROM graph_edges WHERE target = ? AND edge_type = 'prerequisite_of'",
                (topic_id,)
            ).fetchall()
            
            prereq_ids = {p[0] for p in prereqs}
            if prereq_ids and prereq_ids.issubset(studied):
                props = json.loads(props_json)
                recommendations.append({
                    "topic": topic_id,
                    "reason": "Prerequisites met",
                    "properties": props,
                })

        conn.close()
        return recommendations[:10]

    def get_knowledge_gaps(self, user_id: str) -> List[Dict[str, Any]]:
        """Find concepts that are prerequisites of mastered topics but not yet learned."""
        conn = sqlite3.connect(self.db_path)
        
        mastered = set()
        rows = conn.execute(
            "SELECT target FROM graph_edges WHERE source = ? AND edge_type = 'mastered'",
            (user_id,)
        ).fetchall()
        for row in rows:
            mastered.add(row[0])

        gaps = []
        for topic in mastered:
            prereqs = conn.execute(
                "SELECT source FROM graph_edges WHERE target = ? AND edge_type = 'prerequisite_of'",
                (topic,)
            ).fetchall()
            for (prereq,) in prereqs:
                if prereq not in mastered:
                    gaps.append({
                        "concept": prereq,
                        "needed_for": topic,
                        "priority": "high",
                    })

        conn.close()
        return gaps

    def record_study(self, user_id: str, topic: str, duration_minutes: float = 0,
                     concepts_covered: Optional[List[str]] = None) -> None:
        """Record a study session."""
        self.add_node(topic, "topic")
        self.add_edge(user_id, topic, "studied", weight=duration_minutes / 60.0,
                     properties={"duration_minutes": duration_minutes, "timestamp": datetime.now().isoformat()})
        
        if concepts_covered:
            for concept in concepts_covered:
                self.add_node(concept, "concept")
                self.add_edge(topic, concept, "covers")
                self.add_edge(user_id, concept, "studied")

    def record_mastery(self, user_id: str, concept: str, score: float) -> None:
        """Record mastery of a concept."""
        self.add_node(concept, "concept")
        edge_type = "mastered" if score >= 0.8 else "struggling_with" if score < 0.5 else "studied"
        self.add_edge(user_id, concept, edge_type, weight=score)

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user's knowledge statistics."""
        conn = sqlite3.connect(self.db_path)
        
        studied = conn.execute(
            "SELECT COUNT(DISTINCT target) FROM graph_edges WHERE source = ? AND edge_type = 'studied'",
            (user_id,)
        ).fetchone()[0]
        
        mastered = conn.execute(
            "SELECT COUNT(DISTINCT target) FROM graph_edges WHERE source = ? AND edge_type = 'mastered'",
            (user_id,)
        ).fetchone()[0]
        
        struggling = conn.execute(
            "SELECT COUNT(DISTINCT target) FROM graph_edges WHERE source = ? AND edge_type = 'struggling_with'",
            (user_id,)
        ).fetchone()[0]
        
        total_time = conn.execute(
            "SELECT SUM(weight) FROM graph_edges WHERE source = ? AND edge_type = 'studied'",
            (user_id,)
        ).fetchone()[0] or 0

        conn.close()
        return {
            "topics_studied": studied,
            "concepts_mastered": mastered,
            "concepts_struggling": struggling,
            "total_hours": round(total_time, 1),
        }

    def visualize_graph(self, user_id: str, max_nodes: int = 30) -> str:
        """Generate an ASCII visualization of the user's knowledge graph."""
        conn = sqlite3.connect(self.db_path)
        
        # Get user's connections
        edges = conn.execute(
            """SELECT e.target, e.edge_type, e.weight, n.node_type, n.properties
               FROM graph_edges e JOIN graph_nodes n ON e.target = n.id
               WHERE e.source = ? ORDER BY e.weight DESC LIMIT ?""",
            (user_id, max_nodes)
        ).fetchall()
        conn.close()

        if not edges:
            return "  [No knowledge graph data yet. Start studying with `pitagora study`!]"

        lines = []
        lines.append(f"Knowledge Map for {user_id}")
        lines.append("=" * 50)

        # Group by edge type
        groups: Dict[str, List] = {}
        for target, edge_type, weight, node_type, props_json in edges:
            groups.setdefault(edge_type, []).append((target, weight, node_type))

        colors = {"mastered": "🟢", "studied": "🔵", "struggling_with": "🔴", "interested_in": "⚪"}
        
        for edge_type, nodes in groups.items():
            icon = colors.get(edge_type, "⚪")
            lines.append(f"\n{icon} {edge_type.replace('_', ' ').title()}:")
            for name, weight, node_type in nodes:
                bar_len = min(int(weight * 10), 20)
                bar = "█" * bar_len + "░" * (10 - bar_len)
                lines.append(f"  ├─ {name} [{node_type}] {bar} {weight:.1f}")

        return "\n".join(lines)
