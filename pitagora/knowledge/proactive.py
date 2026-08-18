"""Proactive Learner — Autonomous knowledge acquisition and personalized study orchestration.

Following the ponytail minimalism philosophy:
- Zero God Objects: Focuses purely on diagnosing knowledge state, discovering high-signal sources (arXiv, SEP, OpenStax), and synthesizing proactive next-step recommendations.
- Integrates ConceptGraph, MasteryTracker, SpacedRepetition, and KnowledgeAcquisition.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

from pitagora.concepts.graph import ConceptGraph
from pitagora.concepts.tracker import MasteryTracker
from pitagora.knowledge.acquisition import KnowledgeAcquisition
from pitagora.memory.spaced_repetition import SpacedRepetition

log = logging.getLogger(__name__)


@dataclass
class ProactiveDiagnosis:
    """Snapshot of learner state, gaps, and next proactive learning opportunities."""

    mastered_count: int
    in_progress_count: int
    due_reviews: list[str]
    zpd_candidates: list[dict[str, Any]]
    bottlenecks: list[dict[str, Any]]
    recommended_topic: str | None
    recommended_reason: str
    discovered_sources: list[dict[str, Any]] = field(default_factory=list)


class ProactiveLearner:
    """Autonomous engine that drives personalized learning without constant user steering."""

    def __init__(
        self,
        concept_graph: ConceptGraph | None = None,
        mastery_tracker: MasteryTracker | None = None,
        spaced_rep: SpacedRepetition | None = None,
        knowledge_acq: KnowledgeAcquisition | None = None,
    ):
        self.cg = concept_graph or ConceptGraph()
        self.tracker = mastery_tracker or MasteryTracker(concept_graph=self.cg)
        self.spaced_rep = spaced_rep or SpacedRepetition()
        self.acq = knowledge_acq or KnowledgeAcquisition(concept_graph=self.cg)

    def diagnose(self, target_domains: list[str] | None = None) -> ProactiveDiagnosis:
        """Analyze current knowledge state, decay schedules, and determine next optimal step."""
        mastered: list[str] = []
        in_progress: list[str] = []
        zpd_candidates: list[dict[str, Any]] = []
        bottlenecks: list[dict[str, Any]] = []

        # 1. Identify due reviews from spaced repetition
        due_cards = self.spaced_rep.get_due_reviews()
        due_concept_ids = [card.get("concept") or card.get("concept_id") or card.get("id", "") for card in due_cards]
        due_concept_ids = [c for c in due_concept_ids if c]

        # 2. Scan concept graph
        for cid, node in self.cg.graph.items():
            domain = node.get("domain", "")
            if target_domains and domain not in target_domains:
                continue

            score = self.tracker.get_mastery(cid)
            if score >= 0.8:
                mastered.append(cid)
            elif score > 0.0:
                in_progress.append(cid)

            prereqs = node.get("prerequisites", [])
            if prereqs:
                unmet = [p for p in prereqs if self.tracker.get_mastery(p) < 0.7]
                if unmet:
                    # Prereq bottleneck
                    bottlenecks.append({
                        "concept": cid,
                        "name": node.get("name", cid),
                        "domain": domain,
                        "unmet_prerequisites": unmet,
                    })
                elif score < 0.8:
                    # In ZPD!
                    zpd_candidates.append({
                        "concept": cid,
                        "name": node.get("name", cid),
                        "domain": domain,
                        "mastery": score,
                        "prereqs": prereqs,
                    })
            elif score < 0.8:
                # Fundamental root concept in ZPD
                zpd_candidates.append({
                    "concept": cid,
                    "name": node.get("name", cid),
                    "domain": domain,
                    "mastery": score,
                    "prereqs": [],
                })

        # 3. Select top proactive recommendation
        rec_topic = None
        rec_reason = ""

        if due_concept_ids:
            rec_topic = due_concept_ids[0]
            rec_reason = f"Concept '{rec_topic}' is due for spaced repetition review to prevent memory decay."
        elif zpd_candidates:
            # Sort by highest current progress or least prereqs
            zpd_candidates.sort(key=lambda x: x.get("mastery", 0.0), reverse=True)
            top_cand = zpd_candidates[0]
            rec_topic = top_cand["name"]
            rec_reason = f"Ready to master '{rec_topic}' — all prerequisites are satisfied."
        elif bottlenecks:
            # Focus on the most common bottleneck prerequisite
            unmet_counts: dict[str, int] = {}
            for b in bottlenecks:
                for p in b["unmet_prerequisites"]:
                    unmet_counts[p] = unmet_counts.get(p, 0) + 1
            top_unmet = max(unmet_counts.keys(), key=lambda k: unmet_counts[k])
            node_info = self.cg.graph.get(top_unmet, {})
            rec_topic = node_info.get("name", top_unmet)
            rec_reason = f"Mastering '{rec_topic}' will unlock {unmet_counts[top_unmet]} downstream advanced concepts."
        else:
            rec_topic = "Advanced Research"
            rec_reason = "All fundamental concepts mastered. Proactively exploring frontier papers and synthesis."

        return ProactiveDiagnosis(
            mastered_count=len(mastered),
            in_progress_count=len(in_progress),
            due_reviews=due_concept_ids,
            zpd_candidates=zpd_candidates[:5],
            bottlenecks=bottlenecks[:5],
            recommended_topic=rec_topic,
            recommended_reason=rec_reason,
        )

    def prepare_study_context(self, topic: str, auto_fetch: bool = True) -> dict[str, Any]:
        """Fetch papers, open texts, and build a proactive study context for a session."""
        sources: list[dict[str, Any]] = []

        if auto_fetch:
            try:
                # Query arXiv and general academic sources
                papers = self.acq.search_papers(topic, max_results=3)
                for p in papers:
                    sources.append({
                        "type": "paper",
                        "title": p.get("title", ""),
                        "url": p.get("url", ""),
                        "snippet": p.get("snippet", ""),
                    })
            except Exception as e:
                log.debug("Proactive source fetch failed: %s", e)

        return {
            "topic": topic,
            "generated_at": datetime.now(UTC).isoformat(),
            "sources": sources,
        }
