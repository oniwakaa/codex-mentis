import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from sqlite_utils import Database
from codex_mentis.core.models import ReviewCard

class SpacedRepetition:
    def __init__(self, db_path: str = "~/.codex-mentis/memory.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        db = Database(self.db_path)
        if not db["spaced_reviews"].exists():
            db["spaced_reviews"].create({
                "concept": str,
                "ease_factor": float,
                "interval": int,
                "repetitions": int,
                "next_review": str,
                "last_reviewed": str
            }, pk="concept")

    def get_review_metrics(self, concept: str) -> Dict[str, Any]:
        """
        Retrieves SM-2 parameters for a concept.
        Returns default values if not found.
        """
        db = Database(self.db_path)
        try:
            row = db["spaced_reviews"].get(concept)
            return {
                "concept": row["concept"],
                "ease_factor": row["ease_factor"],
                "interval": row["interval"],
                "repetitions": row["repetitions"],
                "next_review": row["next_review"],
                "last_reviewed": row.get("last_reviewed")
            }
        except Exception:
            return {
                "concept": concept,
                "ease_factor": 2.5,
                "interval": 0,
                "repetitions": 0,
                "next_review": date.today().strftime("%Y-%m-%d"),
                "last_reviewed": None
            }

    def schedule_review(self, concept: str, quality: int, mastery_tracker: Optional[Any] = None) -> date:
        """
        Applies the SM-2 algorithm to schedule the next review date for a concept.
        quality: 0 (complete blackout) to 5 (perfect response)
        Updates the concept mastery tracker if integrated.
        """
        quality = max(0, min(5, quality))
        metrics = self.get_review_metrics(concept)
        
        ef = metrics["ease_factor"]
        interval = metrics["interval"]
        reps = metrics["repetitions"]

        # SM-2 logic
        if quality >= 3:
            if reps == 0:
                interval = 1
            elif reps == 1:
                interval = 6
            else:
                interval = int(round(interval * ef))
            reps += 1
        else:
            reps = 0
            interval = 1

        # Update Ease Factor
        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if ef < 1.3:
            ef = 1.3

        today = date.today()
        next_review_date = today + timedelta(days=interval)
        
        db = Database(self.db_path)
        db["spaced_reviews"].insert({
            "concept": concept,
            "ease_factor": ef,
            "interval": interval,
            "repetitions": reps,
            "next_review": next_review_date.strftime("%Y-%m-%d"),
            "last_reviewed": today.strftime("%Y-%m-%d")
        }, replace=True)

        # Integration with concept mastery tracking
        if mastery_tracker:
            try:
                # Map quality [0-5] to performance [0.0-1.0]
                performance = quality / 5.0
                mastery_tracker.update_mastery(concept, performance)
            except Exception:
                pass

        return next_review_date

    def update_score(self, concept: str, quality: int, mastery_tracker: Optional[Any] = None) -> date:
        """Wrapper around schedule_review for backward compatibility."""
        return self.schedule_review(concept, quality, mastery_tracker)

    def get_due_reviews(self) -> List[Dict[str, Any]]:
        """
        Returns a list of all concepts due for review (next_review <= today).
        """
        today_str = date.today().strftime("%Y-%m-%d")
        db = Database(self.db_path)
        try:
            rows = db["spaced_reviews"].rows_where("next_review <= ?", [today_str])
            return [
                {
                    "concept": row["concept"],
                    "ease_factor": row["ease_factor"],
                    "interval": row["interval"],
                    "repetitions": row["repetitions"],
                    "next_review": row["next_review"],
                    "last_reviewed": row.get("last_reviewed")
                }
                for row in rows
            ]
        except Exception:
            return []

    # --- Deck management ---
    def get_deck(self, concept_graph: Any) -> Dict[str, List[str]]:
        """
        Categorizes all concepts in the concept graph into:
        - 'new': not yet in spaced_reviews database
        - 'learning': in spaced_reviews but repetitions == 0 (learning phase or reset)
        - 'review': in spaced_reviews with repetitions > 0
        """
        db = Database(self.db_path)
        try:
            reviewed_concepts = {row["concept"]: row for row in db["spaced_reviews"].rows}
        except Exception:
            reviewed_concepts = {}

        deck = {
            "new": [],
            "learning": [],
            "review": []
        }

        # ConceptGraph has concepts in graph dictionary
        for concept in concept_graph.graph.keys():
            if concept not in reviewed_concepts:
                deck["new"].append(concept)
            else:
                row = reviewed_concepts[concept]
                if row["repetitions"] == 0:
                    deck["learning"].append(concept)
                else:
                    deck["review"].append(concept)
        return deck

    # --- Performance analytics ---
    def get_performance_analytics(self) -> Dict[str, Any]:
        """
        Calculates and returns performance analytics from reviews.
        """
        db = Database(self.db_path)
        try:
            rows = list(db["spaced_reviews"].rows)
        except Exception:
            rows = []

        if not rows:
            return {
                "total_cards": 0,
                "avg_ease_factor": 2.5,
                "avg_interval": 0.0,
                "due_today": 0,
                "learning_count": 0,
                "review_count": 0
            }

        total_cards = len(rows)
        sum_ef = sum(row["ease_factor"] for row in rows)
        sum_interval = sum(row["interval"] for row in rows)
        
        today_str = date.today().strftime("%Y-%m-%d")
        due_today = sum(1 for row in rows if row["next_review"] <= today_str)
        learning_count = sum(1 for row in rows if row["repetitions"] == 0)
        review_count = total_cards - learning_count

        return {
            "total_cards": total_cards,
            "avg_ease_factor": sum_ef / total_cards,
            "avg_interval": sum_interval / total_cards,
            "due_today": due_today,
            "learning_count": learning_count,
            "review_count": review_count
        }
