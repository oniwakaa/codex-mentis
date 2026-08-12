import sqlite3
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class Stats:
    success_rate: float
    avg_confidence: float
    use_count: int

class SkillEvolution:
    def __init__(self, db_path: str = "skills_evolution.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skill_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT,
                success BOOLEAN,
                confidence REAL,
                feedback TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skill_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT,
                prompt_template TEXT,
                version INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def record_use(self, skill_name: str, success: bool, feedback: str, confidence: float = 1.0) -> None:
        """Records a single usage instance of a skill with feedback and success rate."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO skill_usage (skill_name, success, confidence, feedback) VALUES (?, ?, ?, ?)",
                (skill_name, 1 if success else 0, confidence, feedback)
            )
            conn.commit()
        finally:
            conn.close()

    def get_stats(self, skill_name: str) -> Stats:
        """Calculates success rate, average confidence, and usage counts for a skill."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT success, confidence FROM skill_usage WHERE skill_name = ?",
            (skill_name,)
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return Stats(success_rate=0.0, avg_confidence=0.0, use_count=0)

        use_count = len(rows)
        successes = sum(1 for row in rows if row[0])
        success_rate = successes / use_count
        avg_confidence = sum(row[1] for row in rows) / use_count

        return Stats(
            success_rate=success_rate,
            avg_confidence=avg_confidence,
            use_count=use_count
        )

    def evolve_prompt(self, skill_name: str, base_template: str) -> str:
        """Evolves the prompt template by embedding lessons learned from failures and feedback."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Retrieve all feedback for failed runs
        cursor.execute(
            "SELECT feedback FROM skill_usage WHERE skill_name = ? AND success = 0 ORDER BY timestamp DESC LIMIT 10",
            (skill_name,)
        )
        failed_feedbacks = [row[0] for row in cursor.fetchall() if row[0]]
        
        # Get current version
        cursor.execute(
            "SELECT version, prompt_template FROM skill_prompts WHERE skill_name = ? ORDER BY version DESC LIMIT 1",
            (skill_name,)
        )
        row = cursor.fetchone()
        
        current_version = 0
        current_template = base_template
        
        if row:
            current_version = row[0]
            current_template = row[1]
            
        conn.close()

        # If no failed feedbacks, no evolution needed yet
        if not failed_feedbacks:
            return current_template

        # Deterministic prompt evolution: append learned guidelines from failures
        version = current_version + 1
        
        # Parse existing evolved rules if any
        clean_template = current_template
        evolved_marker = "\n### Evolved Guidelines"
        if evolved_marker in clean_template:
            clean_template = clean_template.split(evolved_marker)[0]

        # Construct new evolved guidelines block
        evolved_block = f"{evolved_marker} (V{version}):\n"
        evolved_block += "Based on learning from previous unsuccessful attempts, ensure you strictly adhere to the following:\n"
        for fb in failed_feedbacks:
            # Clean up feedback string to list nicely
            fb_clean = fb.replace("\n", " ").strip()
            evolved_block += f"- Avoid issue: {fb_clean}\n"

        evolved_template = clean_template + evolved_block

        # Save evolved prompt
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO skill_prompts (skill_name, prompt_template, version) VALUES (?, ?, ?)",
                (skill_name, evolved_template, version)
            )
            conn.commit()
        finally:
            conn.close()

        return evolved_template
