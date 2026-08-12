import os
import math
import datetime
from typing import Dict, Any, List, Optional
from sqlite_utils import Database
from pitagora.concepts.graph import ConceptGraph
from pitagora.core.models import ConceptMastery
from pitagora.core.constants import MEMORY_DB

class MasteryTracker:
    def __init__(
        self,
        db_path: str = str(MEMORY_DB),
        concept_graph: Optional[ConceptGraph] = None,
        decay_rate: float = 0.05
    ):
        """
        Tracks concept mastery scores (0.0 to 1.0) in SQLite.
        """
        self.db_path = os.path.expanduser(db_path)
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.concept_graph = concept_graph or ConceptGraph()
        self.decay_rate = decay_rate
        self.db = Database(self.db_path)
        self._init_db()

    def _init_db(self):
        if not self.db["concept_mastery"].exists():
            self.db["concept_mastery"].create({
                "concept": str,
                "mastery_score": float,
                "attempts": int,
                "last_updated": str
            }, pk="concept")

    def get_mastery(self, concept: str, apply_decay: bool = True) -> float:
        """
        Retrieve mastery score for a concept, applying the forgetting curve decay if requested.
        """
        db = self.db
        try:
            row = db["concept_mastery"].get(concept)
            score = row["mastery_score"]
            if not apply_decay:
                return score

            last_updated_str = row["last_updated"]
            last_updated = datetime.datetime.strptime(last_updated_str, "%Y-%m-%d %H:%M:%S")
            days_elapsed = (datetime.datetime.now() - last_updated).total_seconds() / (24.0 * 3600.0)
            
            # Forgetting curve: S = S_0 * e^(-d * t)
            decayed_score = score * math.exp(-self.decay_rate * max(0.0, days_elapsed))
            return max(0.0, min(1.0, decayed_score))
        except Exception:
            return 0.0

    def update_mastery(self, concept: str, performance: float, spaced_rep: Optional[Any] = None):
        """
        Updates the mastery score using an Exponential Moving Average (EMA).
        performance: float in range [0.0, 1.0] representing success rate.
        If spaced_rep is provided, schedules a review dynamically based on performance.
        """
        performance = max(0.0, min(1.0, performance))
        db = self.db
        
        try:
            row = db["concept_mastery"].get(concept)
            current_score = row["mastery_score"]
            attempts = row["attempts"] + 1
            # EMA update: weight current score heavily but allow progression
            new_score = current_score * 0.75 + performance * 0.25
        except Exception:
            new_score = performance
            attempts = 1
            
        new_score = max(0.0, min(1.0, new_score))
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        db["concept_mastery"].insert({
            "concept": concept,
            "mastery_score": new_score,
            "attempts": attempts,
            "last_updated": now_str
        }, replace=True)

        # Integration with spaced repetition
        if spaced_rep:
            try:
                # Map performance [0.0, 1.0] to quality rating [0, 5]
                quality = int(round(performance * 5.0))
                # Call schedule_review, passing self as mastery_tracker=None to avoid recursion
                spaced_rep.schedule_review(concept, quality, mastery_tracker=None)
            except Exception:
                pass

    def get_weak_areas(self, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Get list of concepts with mastery score less than the threshold.
        """
        db = self.db
        try:
            rows = list(db["concept_mastery"].rows)
        except Exception:
            rows = []
            
        weak = []
        for row in rows:
            decayed = self.get_mastery(row["concept"], apply_decay=True)
            if decayed < threshold:
                weak.append({
                    "concept": row["concept"],
                    "mastery_score": decayed,
                    "attempts": row["attempts"]
                })
        return weak

    def get_strong_areas(self, threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Get list of concepts with mastery score greater than or equal to the threshold.
        """
        db = self.db
        try:
            rows = list(db["concept_mastery"].rows)
        except Exception:
            rows = []
            
        strong = []
        for row in rows:
            decayed = self.get_mastery(row["concept"], apply_decay=True)
            if decayed >= threshold:
                strong.append({
                    "concept": row["concept"],
                    "mastery_score": decayed,
                    "attempts": row["attempts"]
                })
        return strong

    def get_overall_progress(self, domain: Optional[str] = None) -> float:
        """
        Calculates the average decayed mastery across concepts.
        If domain is specified, filters by concepts within that domain.
        """
        target_concepts = []
        for name, details in self.concept_graph.graph.items():
            if not domain or details.get("domain", "").lower() == domain.lower():
                target_concepts.append(name)
                
        if not target_concepts:
            return 0.0

        total_mastery = 0.0
        for concept in target_concepts:
            total_mastery += self.get_mastery(concept, apply_decay=True)
            
        return total_mastery / len(target_concepts)

    # --- Progress Report & Analytics ---
    def get_progress_report(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates a comprehensive progress and mastery report.
        """
        target_concepts = []
        for name, details in self.concept_graph.graph.items():
            if not domain or details.get("domain", "").lower() == domain.lower():
                target_concepts.append((name, details))

        mastered = []
        in_progress = []
        not_started = []
        total_time_completed = 0

        for concept, details in target_concepts:
            score = self.get_mastery(concept, apply_decay=True)
            if score >= 0.8:
                mastered.append(concept)
                total_time_completed += details.get("estimated_learning_time", 60)
            elif score > 0.0:
                in_progress.append(concept)
            else:
                not_started.append(concept)

        total_count = len(target_concepts)
        progress_pct = (len(mastered) / total_count) if total_count > 0 else 0.0

        return {
            "domain": domain or "All Domains",
            "progress_percent": progress_pct,
            "mastered_count": len(mastered),
            "mastered_list": mastered,
            "in_progress_count": len(in_progress),
            "in_progress_list": in_progress,
            "not_started_count": len(not_started),
            "not_started_list": not_started,
            "estimated_learning_time_completed_minutes": total_time_completed
        }

    # --- Assessment Generation ---
    def generate_assessment(self, concept: str, num_questions: int = 3) -> Dict[str, Any]:
        """
        Generates structured assessment questions to test concept mastery.
        """
        details = self.concept_graph.graph.get(concept, {})
        if not details:
            return {"error": f"Concept '{concept}' not found in concept graph."}

        prereqs = details.get("prerequisites", [])
        difficulty = details.get("difficulty", 1)
        domain = details.get("domain", "General")

        questions = []
        
        # Q1: Conceptual explanation
        questions.append({
            "id": 1,
            "type": "conceptual",
            "question": f"Explain the core definition and physical/mathematical intuition behind '{concept}'.",
            "rubric": "Check if they define the concept accurately and detail its core mechanics."
        })

        # Q2: Relational question (if has prerequisites)
        if prereqs:
            questions.append({
                "id": 2,
                "type": "relational",
                "question": f"How does the concept of '{concept}' build upon its prerequisite '{prereqs[0]}'? Provide a concrete mathematical mapping or physical system example.",
                "rubric": f"Ensure student demonstrates understanding of the dependency link between '{prereqs[0]}' and '{concept}'."
            })
        else:
            questions.append({
                "id": 2,
                "type": "foundational",
                "question": f"Identify two key fundamental mathematical principles that underpin the study of '{concept}'.",
                "rubric": "Verify references to fundamental axioms, arithmetic or logical structures."
            })

        # Q3: Computational / Problem-solving question
        questions.append({
            "id": 3,
            "type": "computational",
            "question": f"Draft a step-by-step mathematical proof or problem-solving flow showing how you calculate values or derive equations in '{concept}'.",
            "rubric": f"Confirm formal derivation or step-by-step evaluation related to '{concept}'."
        })

        return {
            "concept": concept,
            "domain": domain,
            "difficulty": difficulty,
            "questions": questions[:num_questions]
        }
