import sqlite3
import os
import datetime
from typing import Dict, Any, List, Optional
from codex_mentis.concepts.graph import ConceptGraph

class MasteryTracker:
    def __init__(self, db_path: str = "~/.codex-mentis/memory.db", concept_graph: Optional[ConceptGraph] = None):
        """
        Tracks concept mastery scores (0.0 to 1.0) in SQLite.
        """
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.concept_graph = concept_graph or ConceptGraph()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS concept_mastery (
                    concept TEXT PRIMARY KEY,
                    mastery_score REAL DEFAULT 0.0,
                    attempts INTEGER DEFAULT 0,
                    last_updated TEXT
                )
            """)
            conn.commit()

    def get_mastery(self, concept: str) -> float:
        """
        Retrieve mastery score for a concept, defaulting to 0.0 if not started.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mastery_score FROM concept_mastery WHERE concept = ?", (concept,))
            row = cursor.fetchone()
        return row[0] if row else 0.0

    def update_mastery(self, concept: str, performance: float):
        """
        Updates the mastery score using an Exponential Moving Average (EMA).
        performance: float in range [0.0, 1.0] representing success rate or rating.
        """
        performance = max(0.0, min(1.0, performance))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mastery_score, attempts FROM concept_mastery WHERE concept = ?", (concept,))
            row = cursor.fetchone()
            
            if row:
                current_score, attempts = row
                # EMA update: weight current score heavily but allow progression
                new_score = current_score * 0.75 + performance * 0.25
                attempts += 1
            else:
                new_score = performance
                attempts = 1
                
            new_score = max(0.0, min(1.0, new_score))
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                INSERT OR REPLACE INTO concept_mastery (concept, mastery_score, attempts, last_updated)
                VALUES (?, ?, ?, ?)
            """, (concept, new_score, attempts, now_str))
            conn.commit()

    def get_weak_areas(self, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Get list of concepts with mastery score less than the threshold.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT concept, mastery_score, attempts FROM concept_mastery WHERE mastery_score < ?", 
                (threshold,)
            )
            rows = cursor.fetchall()
            
        return [
            {"concept": row[0], "mastery_score": row[1], "attempts": row[2]}
            for row in rows
        ]

    def get_strong_areas(self, threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Get list of concepts with mastery score greater than or equal to the threshold.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT concept, mastery_score, attempts FROM concept_mastery WHERE mastery_score >= ?", 
                (threshold,)
            )
            rows = cursor.fetchall()
            
        return [
            {"concept": row[0], "mastery_score": row[1], "attempts": row[2]}
            for row in rows
        ]

    def get_overall_progress(self, domain: Optional[str] = None) -> float:
        """
        Calculates the average mastery across concepts.
        If domain is specified, filters by concepts within that domain.
        """
        # Filter concept list by domain
        target_concepts = []
        for name, details in self.concept_graph.graph.items():
            if not domain or details.get("domain", "").lower() == domain.lower():
                target_concepts.append(name)
                
        if not target_concepts:
            return 0.0

        total_mastery = 0.0
        for concept in target_concepts:
            total_mastery += self.get_mastery(concept)
            
        return total_mastery / len(target_concepts)
