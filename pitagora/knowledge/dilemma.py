"""Philosophical Thought Experiments & Dilemma Simulation Engine.

Provides structured philosophical thought experiments across Metaphysics,
Philosophy of Mind, Ethics, Epistemology, and the Physics-Philosophy intersection.
Runs interactive Socratic probing and calculates Epistemic Consistency across choices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class DilemmaChoice:
    key: str
    label: str
    philosophical_stance: str
    implications: str
    counter_probe: str


@dataclass
class DilemmaScenario:
    id: str
    title: str
    domain: str
    premise: str
    choices: list[DilemmaChoice]
    deep_reflection: str
    traditions: list[str] = field(default_factory=list)


BUILTIN_DILEMMAS: dict[str, DilemmaScenario] = {
    "ship_of_theseus": DilemmaScenario(
        id="ship_of_theseus",
        title="The Ship of Theseus & Continuous Identity",
        domain="Metaphysics & Ontology",
        premise=(
            "A wooden ship sails across the Aegean. Over decades, every plank, mast, and nail "
            "is replaced one by one with new wood until zero original atoms remain. "
            "Meanwhile, a collector gathers all the discarded old planks and rebuilds a ship with them."
        ),
        choices=[
            DilemmaChoice(
                key="A",
                label="The renovated sailing ship is the true Ship of Theseus.",
                philosophical_stance="Functional Continuity / Spatiotemporal Continuity (Hobbes/Locke)",
                implications="Identity is preserved through continuous functional and historical trajectory, not material constitution.",
                counter_probe="If continuity defines identity, what happens if the ship is disassembled for 10 years before reassembly?",
            ),
            DilemmaChoice(
                key="B",
                label="The reconstructed ship from old planks is the true Ship of Theseus.",
                philosophical_stance="Mereological Essentialism (Chisholm)",
                implications="An object's identity is strictly identical to the sum of its original constituent parts.",
                counter_probe="Since your biological cells replace themselves every 7-10 years, are you no longer the person born with your name?",
            ),
            DilemmaChoice(
                key="C",
                label="Neither or both (Identity over time is an epistemic linguistic convention, not fundamental ontology).",
                philosophical_stance="Four-Dimensionalism / Conventionalism (Sider/Parfit)",
                implications="Objects are 4D spacetime worms; 'sameness' is a pragmatic language construct rather than a hard ontological fact.",
                counter_probe="If personal identity is purely conventional, on what ontological basis do we hold someone legally responsible for past actions?",
            ),
        ],
        deep_reflection=(
            "The Ship of Theseus bridges classical Greek metaphysics with modern quantum ontology: "
            "at the fundamental level, particles of the same quantum state are indistinguishable excitations "
            "of quantum fields, making absolute material continuity physically ill-defined."
        ),
        traditions=["Plato", "Thomas Hobbes", "John Locke", "Derek Parfit", "Theodore Sider"],
    ),
    "chinese_room": DilemmaScenario(
        id="chinese_room",
        title="The Chinese Room & Semantic Intentionality",
        domain="Philosophy of Mind & AI",
        premise=(
            "An English speaker who understands zero Chinese sits in a sealed room with a rulebook. "
            "Chinese characters are slipped in through a slot. Following purely syntactic lookup rules, "
            "the person outputs corresponding Chinese characters indistinguishable from a native speaker."
        ),
        choices=[
            DilemmaChoice(
                key="A",
                label="The person does not understand Chinese; syntax alone cannot generate semantics or intentionality.",
                philosophical_stance="Biological Naturalism / Anti-Computationalism (Searle)",
                implications="Symbol manipulation is fundamentally insufficient for genuine comprehension, qualia, or consciousness.",
                counter_probe="If individual neurons don't understand English, why does the whole biological system understand English?",
            ),
            DilemmaChoice(
                key="B",
                label="The room as a unified system (person + rules + memory) DOES understand Chinese.",
                philosophical_stance="Systems Reply / Computational Functionalism (Dennett/Churchland)",
                implications="Understanding is an emergent property of information processing across the entire cognitive architecture.",
                counter_probe="If the person memorizes the entire rulebook and runs it in their head, they still experience zero understanding of the meaning of the words. Where is the comprehension located?",
            ),
            DilemmaChoice(
                key="C",
                label="Understanding is behavioral and functional; if behavior is indistinguishable, distinction between syntax and semantics dissolves.",
                philosophical_stance="Radical Functionalism / Turing Criterion",
                implications="Intelligent behavior is the operational definition of understanding; internal subjective qualia are epiphenomenal.",
                counter_probe="Can a lookup table with infinite pre-computed answers truly be said to 'understand' a mathematical proof?",
            ),
        ],
        deep_reflection=(
            "Searle's argument cuts directly to modern LLMs: does statistical token next-prediction "
            "constitute world-model comprehension or pure formal syntactic orchestration?"
        ),
        traditions=["John Searle", "Daniel Dennett", "Alan Turing", "Patricia Churchland", "Ned Block"],
    ),
    "maxwells_demon": DilemmaScenario(
        id="maxwells_demon",
        title="Maxwell's Demon & Information Thermodynamics",
        domain="Physics & Philosophy of Science",
        premise=(
            "A microscopic demon controls a door between two chambers of gas, letting fast (hot) particles "
            "go left and slow (cold) particles go right, seemingly decreasing entropy without doing mechanical work."
        ),
        choices=[
            DilemmaChoice(
                key="A",
                label="The Demon proves the Second Law of Thermodynamics is statistical, not absolute.",
                philosophical_stance="Statistical Indeterminism (Boltzmann)",
                implications="Entropy decrease is not physically impossible, merely overwhelmingly improbable.",
                counter_probe="If it is merely statistical, could an automated nano-gate extract free energy indefinitely from ambient heat?",
            ),
            DilemmaChoice(
                key="B",
                label="The Demon must store and erase information, and Landauer's Principle dictates memory erasure generates thermodynamic heat.",
                philosophical_stance="Information Physicalism (Landauer/Bennett/Szilard)",
                implications="'Information is Physical'. Acquiring and resetting the Demon's memory registers preserves ΔS_total ≥ 0.",
                counter_probe="What if the Demon never erases its memory, using an unbounded quantum tape?",
            ),
            DilemmaChoice(
                key="C",
                label="Entropy is an observer-dependent measure of epistemic ignorance, not an intrinsic physical substance.",
                philosophical_stance="Epistemic Bayesian Thermodynamics (Jaynes)",
                implications="Entropy quantifies the observer's missing information about microstates given macro observables.",
                counter_probe="If entropy is observer-dependent, how does the universe exhibit an objective arrow of time independent of minds?",
            ),
        ],
        deep_reflection=(
            "Maxwell's Demon illustrates the profound synthesis of physics, computation, and epistemology: "
            "Shannon information entropy H and thermodynamic Boltzmann entropy S are fundamentally coupled by k_B ln(2)."
        ),
        traditions=["James Clerk Maxwell", "Leo Szilard", "Rolf Landauer", "Charles Bennett", "E.T. Jaynes"],
    ),
    "trolley_fatman": DilemmaScenario(
        id="trolley_fatman",
        title="The Trolley Problem & Doctrine of Double Effect",
        domain="Normative & Applied Ethics",
        premise=(
            "A runaway trolley is barreling toward 5 workers. In Case 1 (Switch), you can divert the train onto a track with 1 worker. "
            "In Case 2 (Footbridge), you can only stop the train by pushing a heavy bystander off a bridge into the train's path."
        ),
        choices=[
            DilemmaChoice(
                key="A",
                label="Divert the switch AND push the heavy bystander (1 death is always mathematically better than 5).",
                philosophical_stance="Act Utilitarianism / Consequentialism (Bentham/Singer)",
                implications="Moral value resides strictly in net welfare outcomes; means are subordinate to minimizing total suffering.",
                counter_probe="Would you support a surgeon secretly killing 1 healthy patient to harvest organs for 5 dying patients?",
            ),
            DilemmaChoice(
                key="B",
                label="Divert the switch in Case 1, but DO NOT push the bystander in Case 2.",
                philosophical_stance="Doctrine of Double Effect / Deontological Threshold (Foot/Thomson)",
                implications="Foreseeing harm as a side-effect is morally distinct from intentionally using a human being as a mere physical instrument.",
                counter_probe="Why should the physical geometry of causal involvement override the identical mathematical outcome of human lives saved?",
            ),
            DilemmaChoice(
                key="C",
                label="Do not intervene in either case; active killing is categorically prohibited compared to allowing natural events to unfold.",
                philosophical_stance="Strict Kantian Absolutism / Non-Interventionist Deontology",
                implications="Categorical duties forbid causing direct harm regardless of collateral consequences.",
                counter_probe="If failing to flip a switch knowingly causes 5 preventable deaths, does omission not constitute a conscious moral choice?",
            ),
        ],
        deep_reflection=(
            "Ethical decision models reveal our implicit algorithmic commitments: "
            "whether human value is additive/optimizable (Utilitarian) or protected by inviolable axiomatic constraints (Kantian)."
        ),
        traditions=["Philippa Foot", "Judith Jarvis Thomson", "Jeremy Bentham", "Immanuel Kant", "Peter Singer"],
    ),
    "newcomb_problem": DilemmaScenario(
        id="newcomb_problem",
        title="Newcomb's Paradox & The Foundations of Decision Theory",
        domain="Decision Theory & Epistemology",
        premise=(
            "A superintelligent Predictor with 99.99% accuracy places $1,000 in Box A. "
            "In Box B, it places either $1,000,000 or $0. "
            "If it predicted you will take ONLY Box B (One-Box), it put $1,000,000 in Box B. "
            "If it predicted you will take BOTH boxes (Two-Box), it left Box B empty. "
            "The prediction is already made and the boxes are sealed in front of you."
        ),
        choices=[
            DilemmaChoice(
                key="A",
                label="Take only Box B (One-Boxing).",
                philosophical_stance="Evidential Decision Theory (EDT) / Backward Induction",
                implications="Choose the action that provides the strongest evidence for the best state of affairs ($1M).",
                counter_probe="The money is ALREADY in the box or not. How can your current physical choice retroactively change what is inside a sealed box?",
            ),
            DilemmaChoice(
                key="B",
                label="Take both Box A and Box B (Two-Boxing).",
                philosophical_stance="Causal Decision Theory (CDT) / Dominance Principle",
                implications="Whatever is in Box B is fixed. Dominance dictates you get whatever is in B PLUS $1,000 in A.",
                counter_probe="If Two-Boxers walk away with $1,000 and One-Boxers walk away with $1,000,000, why is the 'rational' CDT agent consistently poorer?",
            ),
        ],
        deep_reflection=(
            "Newcomb's problem exposes a deep rift in rational agency: "
            "should an agent act to cause desired outcomes (CDT), or act as a reliable signal of them (EDT)?"
        ),
        traditions=["Robert Nozick", "David Lewis", "Allan Gibbard", "Ehud Kalai"],
    ),
}


class DilemmaEngine:
    """Manages philosophical dilemma simulation, Socratic exploration, and consistency profiling."""

    def __init__(self, chat_completion_fn: Callable[..., str] | None = None):
        self._chat = chat_completion_fn
        self.history: list[dict[str, Any]] = []
        self.stances_taken: dict[str, str] = {}

    def get_scenario(self, scenario_id: str) -> DilemmaScenario | None:
        return BUILTIN_DILEMMAS.get(scenario_id.lower().replace("-", "_"))

    def list_scenarios(self) -> list[dict[str, str]]:
        return [
            {
                "id": s.id,
                "title": s.title,
                "domain": s.domain,
            }
            for s in BUILTIN_DILEMMAS.values()
        ]

    def record_choice(self, scenario_id: str, choice_key: str) -> dict[str, Any]:
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return {"error": f"Unknown scenario '{scenario_id}'"}

        selected = next((c for c in scenario.choices if c.key.upper() == choice_key.upper()), None)
        if not selected:
            return {"error": f"Invalid choice '{choice_key}' for {scenario.title}"}

        self.stances_taken[scenario.id] = selected.philosophical_stance
        self.history.append({
            "scenario": scenario.id,
            "choice": selected.key,
            "stance": selected.philosophical_stance,
        })

        return {
            "scenario": scenario.title,
            "stance": selected.philosophical_stance,
            "implications": selected.implications,
            "counter_probe": selected.counter_probe,
            "deep_reflection": scenario.deep_reflection,
            "traditions": scenario.traditions,
        }

    def compute_epistemic_profile(self) -> dict[str, Any]:
        """Analyzes consistency and metaphysical/ethical orientations across chosen stances."""
        stances = list(self.stances_taken.values())
        total = len(stances)

        is_consequentialist = any("Utilitarianism" in s for s in stances)
        is_deontologist = any("Deontological" in s or "Kantian" in s for s in stances)
        is_functionalist = any("Functional" in s for s in stances)
        is_essentialist = any("Essentialism" in s for s in stances)

        tensions = []
        if is_consequentialist and is_deontologist:
            tensions.append("Hybrid Ethical Framework: Blends utilitarian outcomes with deontological constraints.")
        if is_functionalist and is_essentialist:
            tensions.append("Ontological Tension: Appeals to functional continuity in some contexts and strict essentialism in others.")

        return {
            "completed_scenarios": total,
            "stances_registered": self.stances_taken,
            "tensions_detected": tensions,
            "summary": (
                f"Completed {total} thought experiments. "
                + (f"Identified {len(tensions)} philosophical tensions." if tensions else "Consistent epistemic commitments.")
            ),
        }
