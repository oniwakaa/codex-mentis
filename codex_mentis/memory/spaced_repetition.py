import sqlite3
import os
import datetime
from typing import Dict, Any, List, Optional

class SpacedRepetition:
    def __init__(self, db_path: str = "~/.codex-mentis/memory.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS spaced_reviews (
                    concept TEXT PRIMARY KEY,
                    ease_factor REAL DEFAULT 2.5,
                    interval INTEGER DEFAULT 0,
                    repetitions INTEGER DEFAULT 0,
                    next_review TEXT
                )
            """)
            conn.commit()

    def get_review_metrics(self, concept: str) -> Dict[str, Any]:
        """
        Retrieves SM-2 parameters for a concept.
        Returns default values if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ease_factor, interval, repetitions, next_review FROM spaced_reviews WHERE concept = ?", 
                (concept,)
            )
            row = cursor.fetchone()
            
        if row:
            return {
                "concept": concept,
                "ease_factor": row[0],
                "interval": row[1],
                "repetitions": row[2],
                "next_review": row[3]
            }
        else:
            return {
                "concept": concept,
                "ease_factor": 2.5,
                "interval": 0,
                "repetitions": 0,
                "next_review": datetime.date.today().strftime("%Y-%m-%d")
            }

    def schedule_review(self, concept: str, quality: int) -> datetime.date:
        """
        Applies the SM-2 algorithm to schedule the next review date for a concept.
        quality: 0 (blackout) to 5 (perfect response)
        """
        # Ensure quality is in [0, 5]
        quality = max(0, min(5, quality))
        
        metrics = self.get_review_metrics(concept)
        ef = metrics["ease_factor"]
        interval = metrics["interval"]
        reps = metrics["repetitions"]

        # SM-2 calculation
        if quality >= 3:
            if reps == 0:
                interval = 1
            elif reps == 1:
                interval = 6
            else:
                interval = int(round(interval * ef))
            reps += 1
        else:
            # Failed recall, reset
            reps = 0
            interval = 1

        # Update Ease Factor
        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if ef < 1.3:
            ef = 1.3

        today = datetime.date.today()
        next_review_date = today + datetime.timedelta(days=interval)
        next_review_str = next_review_date.strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO spaced_reviews (concept, ease_factor, interval, repetitions, next_review)
                VALUES (?, ?, ?, ?, ?)
            """, (concept, ef, interval, reps, next_review_str))
            conn.commit()

        return next_review_date

    def get_due_reviews(self) -> List[Dict[str, Any]]:
        """
        Returns a list of all concepts due for review (next_review <= today).
        """
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT concept, ease_factor, interval, repetitions, next_review FROM spaced_reviews WHERE next_review <= ?", 
                (today_str,)
            )
            rows = cursor.fetchall()

        return [
            {
                "concept": row[0],
                "ease_factor": row[1],
                "interval": row[2],
                "repetitions": row[3],
                "next_review": row[4]
            }
            for row in rows
        ]

    def update_score(self, concept: str, quality: int) -> datetime.date:
        """
        Updates the score for a concept, wrapper around schedule_review.
        """
        return self.schedule_review(concept, quality)
