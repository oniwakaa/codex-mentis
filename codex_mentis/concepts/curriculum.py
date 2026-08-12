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
        Suggests the next concept to study using the Zone of Proximal Development (ZPD).
        Finds a concept in the user's ZPD: unmastered (< 0.8) but where prerequisites
        are highly mastered (average >= 0.7).
        """
        candidates = []
        roots_unmastered = []
        
        for concept, details in self.concept_graph.graph.items():
            mastery = self.tracker.get_mastery(concept)
            if mastery >= 0.8:
                continue  # already mastered
                
            prereqs = details.get("prerequisites", [])
            if not prereqs:
                roots_unmastered.append((concept, mastery))
                continue
                
            # Check prerequisites average mastery
            sum_prereq_mastery = 0.0
            all_prereqs_met = True
            for pr in prereqs:
                p_mast = self.tracker.get_mastery(pr)
                sum_prereq_mastery += p_mast
                if p_mast < 0.7:
                    all_prereqs_met = False
            
            avg_prereq_mastery = sum_prereq_mastery / len(prereqs)
            
            if all_prereqs_met:
                # ZPD index is higher when prerequisites are highly mastered
                zpd_index = avg_prereq_mastery - mastery
                candidates.append((concept, zpd_index, details))

        # Suggest candidate in ZPD with the highest score
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            suggested = candidates[0][0]
            reason = f"You have mastered all prerequisites for '{suggested}' and it lies perfectly in your Zone of Proximal Development."
            return {"concept": suggested, "reason": reason, "details": candidates[0][2]}
            
        # Fallback to unmastered roots (basic concepts)
        if roots_unmastered:
            roots_unmastered.sort(key=lambda x: x[1])
            suggested = roots_unmastered[0][0]
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
        utilizing the optimized concept path (excluding mastered concepts).
        """
        if target not in self.concept_graph.graph:
            return [{"error": f"Target concept '{target}' not found in concept graph."}]

        # Gather currently mastered concepts
        mastered_list = [
            c for c in self.concept_graph.graph.keys() 
            if self.tracker.get_mastery(c) >= 0.8
        ]
        
        # Use optimized pathfinder
        needed_concepts = self.concept_graph.get_optimized_path(target, mastered_concepts=mastered_list)
        
        if not needed_concepts:
            return [{"message": f"You have already mastered the target concept '{target}' and all its prerequisites."}]

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
            details = self.concept_graph.graph.get(concept, {})
            schedule.append({
                "concept": concept,
                "description": details.get("description", "Spaced repetition study item"),
                "ease_factor": d["ease_factor"],
                "repetitions": d["repetitions"],
                "next_review": d["next_review"]
            })
        return schedule

    # --- Prerequisite Gap Analysis ---
    def prerequisite_gap_analysis(self, target: str) -> Dict[str, Any]:
        """
        Performs a gap analysis for a target concept, identifying which prerequisites
        have not been met and their current mastery levels.
        """
        if target not in self.concept_graph.graph:
            return {"error": f"Concept '{target}' not found in graph."}

        full_path = self.concept_graph.get_learning_path(target)
        # Exclude target itself
        prereqs_needed = [c for c in full_path if c != target]

        missing = []
        ready = []
        for pr in prereqs_needed:
            score = self.tracker.get_mastery(pr)
            status = {
                "concept": pr,
                "mastery_score": score,
                "domain": self.concept_graph.graph[pr].get("domain", "General")
            }
            if score < 0.7:
                missing.append(status)
            else:
                ready.append(status)

        is_ready = len(missing) == 0
        return {
            "target_concept": target,
            "is_ready_to_study": is_ready,
            "unmet_prerequisites": missing,
            "met_prerequisites": ready
        }

    # --- Milestone Tracking ---
    def get_milestones(self) -> List[Dict[str, Any]]:
        """
        Tracks key learning milestones. Milestones are defined as mastering
        'gateway' concepts (concepts that have 2 or more dependents).
        """
        milestones = []
        for concept, details in self.concept_graph.graph.items():
            dependents = details.get("dependents", [])
            if len(dependents) >= 2:
                # This is a gateway/milestone concept!
                mastery = self.tracker.get_mastery(concept)
                completed = mastery >= 0.8
                milestones.append({
                    "milestone_concept": concept,
                    "description": f"Master {concept} to unlock {', '.join(dependents)}",
                    "completed": completed,
                    "mastery_score": mastery
                })
        return milestones

    # --- Daily Review Scheduling ---
    def get_daily_review_schedule(self, max_reviews: int = 5) -> List[Dict[str, Any]]:
        """
        Generates a limited, prioritized review schedule for the current day.
        Prioritizes items with lower ease factor and higher decay.
        """
        due_reviews = self.get_review_schedule()
        
        # Sort by ease factor ascending (harder cards first), then reps ascending (newer first)
        due_reviews.sort(key=lambda x: (x.get("ease_factor", 2.5), x.get("repetitions", 0)))
        
        return due_reviews[:max_reviews]
