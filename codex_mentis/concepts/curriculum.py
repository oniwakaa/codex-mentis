from typing import Dict, Any, List, Optional
from codex_mentis.concepts.graph import ConceptGraph
from codex_mentis.concepts.tracker import MasteryTracker
from codex_mentis.memory.spaced_repetition import SpacedRepetition

class CurriculumGenerator:
    def __init__(
        self, 
        concept_graph: Optional[ConceptGraph] = None, 
        mastery_tracker: Optional[MasteryTracker] = None,
        spaced_rep: Optional[SpacedRepetition] = None
    ):
        self.concept_graph = concept_graph or ConceptGraph()
        self.tracker = mastery_tracker or MasteryTracker(concept_graph=self.concept_graph)
        self.spaced_rep = spaced_rep or SpacedRepetition()

    def suggest_next(self) -> Dict[str, Any]:
        """
        Suggests the next concept to study.
        Finds a concept that the student hasn't mastered yet (< 0.8)
        but for which all prerequisites have been reasonably mastered (>= 0.7).
        """
        candidates = []
        roots_unmastered = []
        
        for concept, details in self.concept_graph.graph.items():
            mastery = self.tracker.get_mastery(concept)
            if mastery >= 0.8:
                continue  # already mastered
                
            prereqs = details.get("prerequisites", [])
            if not prereqs:
                roots_unmastered.append(concept)
                continue
                
            # Check if all prerequisites are mastered
            all_prereqs_met = True
            for pr in prereqs:
                if self.tracker.get_mastery(pr) < 0.7:
                    all_prereqs_met = False
                    break
                    
            if all_prereqs_met:
                candidates.append((concept, mastery))

        # Suggest candidate with lowest mastery first (or first available)
        if candidates:
            candidates.sort(key=lambda x: x[1])
            suggested = candidates[0][0]
            reason = f"You have mastered all prerequisites for '{suggested}' and are ready to start."
            return {"concept": suggested, "reason": reason, "details": self.concept_graph.graph[suggested]}
            
        # Fallback to unmastered roots (basic concepts)
        if roots_unmastered:
            suggested = roots_unmastered[0]
            reason = f"'{suggested}' is a fundamental concept with no prerequisites that you haven't mastered yet."
            return {"concept": suggested, "reason": reason, "details": self.concept_graph.graph[suggested]}

        return {
            "concept": None,
            "reason": "Congratulations! You have mastered all concepts in the concept graph.",
            "details": {}
        }

    def generate_study_plan(self, target: str, timeline_weeks: int = 4) -> List[Dict[str, Any]]:
        """
        Generates a week-by-week study plan to master a target concept,
        filtering out concepts already mastered.
        """
        if target not in self.concept_graph.graph:
            return [{"error": f"Target concept '{target}' not found in concept graph."}]

        full_path = self.concept_graph.get_learning_path(target)
        
        # Filter down to unmastered items
        needed_concepts = [c for c in full_path if self.tracker.get_mastery(c) < 0.8]
        
        if not needed_concepts:
            return [{"message": f"You have already mastered the target concept '{target}' and all its prerequisites."}]

        # Distribute concepts evenly across timeline weeks
        plan = []
        n_concepts = len(needed_concepts)
        concepts_per_week = max(1, n_concepts // timeline_weeks)
        
        for idx, concept in enumerate(needed_concepts):
            week = min(timeline_weeks, (idx // concepts_per_week) + 1)
            details = self.concept_graph.graph.get(concept, {})
            plan.append({
                "week": week,
                "concept": concept,
                "description": details.get("description", ""),
                "domain": details.get("domain", "")
            })
            
        return plan

    def get_review_schedule(self) -> List[Dict[str, Any]]:
        """
        Retrieves the list of concepts scheduled for review under SM-2 spaced repetition.
        """
        due = self.spaced_rep.get_due_reviews()
        schedule = []
        for d in due:
            concept = d["concept"]
            # Check if this concept exists in the graph to add description
            details = self.concept_graph.graph.get(concept, {})
            schedule.append({
                "concept": concept,
                "description": details.get("description", "Spaced repetition study item"),
                "ease_factor": d["ease_factor"],
                "repetitions": d["repetitions"],
                "next_review": d["next_review"]
            })
        return schedule
