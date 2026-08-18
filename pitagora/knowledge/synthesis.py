"""Cross-domain synthesis engine — bridges Mathematics, Physics, and Philosophy.

Following ponytail minimalism:
- Zero God Objects: pure functional mappings and lightweight synthesis classes.
- Connects formal systems, physical models, and epistemological/metaphysical frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DomainConnection:
    """A conceptual bridge connecting concepts across different domains."""

    source_concept: str
    source_domain: str
    target_concept: str
    target_domain: str
    relation_type: str  # epistemic_foundation, formal_model, ontological_implication, analogical
    description: str
    key_question: str


# Core canonical cross-domain bridges across Math, Physics, and Philosophy
CANONICAL_BRIDGES: list[DomainConnection] = [
    DomainConnection(
        source_concept="mech_lagrangian",
        source_domain="mechanics",
        target_concept="phil_metaphysics",
        target_domain="philosophy",
        relation_type="ontological_implication",
        description=(
            "The Principle of Least Action reformulates mechanics not through local causal forces (Newton) "
            "but through global variational economy (Euler-Lagrange). This mirrors teleological vs mechanical "
            "debates in metaphysics (Leibniz, Maupertuis)."
        ),
        key_question="Does nature optimize a global quantity (action), or are variational principles merely mathematical duals to local differential causation?",
    ),
    DomainConnection(
        source_concept="qm_schrodinger",
        source_domain="quantum",
        target_concept="phil_epistemology",
        target_domain="philosophy",
        relation_type="epistemic_foundation",
        description=(
            "Quantum state superposition and the measurement problem challenge realist epistemology, "
            "intersecting with Kantian phenomena/noumena distinctions and operationalism."
        ),
        key_question="Does the wave function represent physical ontology or an agent's Bayesian state of incomplete information (QBism)?",
    ),
    DomainConnection(
        source_concept="alg_galois",
        source_domain="algebra",
        target_concept="phil_formal_logic",
        target_domain="philosophy",
        relation_type="formal_model",
        description=(
            "Galois theory symmetries of polynomial roots connect deeply with structuralism in philosophy of math "
            "and invariant representations in model theory."
        ),
        key_question="Are mathematical entities defined solely by their relational automorphism groups rather than intrinsic substance?",
    ),
    DomainConnection(
        source_concept="thermo_entropy",
        source_domain="thermodynamics",
        target_concept="phil_epistemology",
        target_domain="philosophy",
        relation_type="ontological_implication",
        description=(
            "Statistical entropy (Boltzmann/Gibbs) connects microstate ignorance with thermodynamic irreversibility, "
            "founding modern debates on Time's Arrow and information ontology (Landauer's Principle)."
        ),
        key_question="Is the arrow of time an objective physical asymmetry or an artifact of macroscopic epistemic coarse-graining?",
    ),
    DomainConnection(
        source_concept="prob_bayesian",
        source_domain="probability",
        target_concept="phil_epistemology",
        target_domain="philosophy",
        relation_type="epistemic_foundation",
        description=(
            "Bayesian updating formalizes rational belief revision under uncertainty, providing a rigorous mathematical "
            "foundation for confirmation theory and inductive logic (Carnap, Jeffrey)."
        ),
        key_question="Can all rational scientific belief revision be reduced to conditional probability updates over a prior distribution?",
    ),
    DomainConnection(
        source_concept="phil_formal_logic",
        source_domain="philosophy",
        target_concept="calc_limits",
        target_domain="calculus",
        relation_type="formal_model",
        description=(
            "Weierstrass (epsilon-delta) formalization of calculus limits resolved centuries of philosophical paradoxes "
            "regarding infinitesimals (Zeno, Berkeley's ghosts of departed quantities) via first-order predicate quantifiers."
        ),
        key_question="How does quantifier alternation (∀ε>0 ∃δ>0) eliminate actual infinitesimals in favor of potential limits?",
    ),
]


class CrossDomainSynthesizer:
    """Discovers, tracks, and generates epistemological and interdisciplinary bridges."""

    def __init__(self, bridges: list[DomainConnection] | None = None) -> None:
        self.bridges = bridges or list(CANONICAL_BRIDGES)

    def find_connections(self, concept_id: str) -> list[DomainConnection]:
        """Find all cross-domain bridges involving a specific concept."""
        cid = concept_id.strip().lower()
        return [
            b
            for b in self.bridges
            if b.source_concept.lower() == cid
            or b.target_concept.lower() == cid
            or cid in b.source_concept.lower()
            or cid in b.target_concept.lower()
        ]

    def bridge_domains(self, domain_a: str, domain_b: str) -> list[DomainConnection]:
        """Find all connections spanning between two domains (e.g. 'mechanics' and 'philosophy')."""
        da, db = domain_a.strip().lower(), domain_b.strip().lower()
        return [
            b
            for b in self.bridges
            if (b.source_domain.lower() == da and b.target_domain.lower() == db)
            or (b.source_domain.lower() == db and b.target_domain.lower() == da)
        ]

    def generate_synthesis_prompt(
        self, concept_name: str, domain: str
    ) -> dict[str, Any]:
        """Synthesizes cross-domain reflection questions for deep Socratic exploration."""
        conns = self.find_connections(concept_name)
        if conns:
            best = conns[0]
            return {
                "concept": concept_name,
                "domain": domain,
                "has_bridge": True,
                "target_concept": best.target_concept,
                "target_domain": best.target_domain,
                "epistemic_context": best.description,
                "socratic_question": best.key_question,
            }

        # Fallback general philosophical synthesis prompt
        return {
            "concept": concept_name,
            "domain": domain,
            "has_bridge": False,
            "target_concept": "epistemology",
            "target_domain": "philosophy",
            "epistemic_context": f"Examine the epistemological status and foundational axioms of {concept_name}.",
            "socratic_question": f"What are the unstated epistemic assumptions or idealizations behind {concept_name}?",
        }
