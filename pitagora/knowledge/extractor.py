"""Knowledge extractor — parses equations, definitions, theorems, and concepts from raw text.

This is the NLP layer that turns crawled web content into structured knowledge.
No LLM calls needed — uses regex heuristics and pattern matching for math/science content.
"""

import re
from typing import Any


class KnowledgeExtractor:
    """Extracts structured knowledge from raw text (papers, articles, wikis)."""

    # Common math definition patterns
    DEFINITION_PATTERNS = [
        r"(?:we\s+)?(?:define|definition)\s*[:.]?\s*(.*?)(?:\.|$)",
        r"(?:a|an|the)\s+(.*?)\s+is\s+(?:defined\s+as|called|said\s+to\s+be)\s+(.*?)(?:\.|$)",
        r"let\s+(.*?)\s+(?:be|denote)\s+(.*?)(?:\.|$)",
    ]

    THEOREM_PATTERNS = [
        r"(?:theorem|lemma|proposition|corollary)\s*[\d.]*\s*[:\(]?\s*(.*?)(?:\)|$)",
        r"(?:theorem|lemma|proposition|corollary)\s*\((.*?)\)",
    ]

    # LaTeX equation patterns
    EQUATION_PATTERNS = [
        # Display math: $$ ... $$ or \[ ... \]
        r"\$\$(.*?)\$\$",
        r"\\\[(.*?)\\\]",
        # \begin{equation} ... \end{equation}
        r"\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}",
        r"\\begin\{align\*?\}(.*?)\\end\{align\*?\}",
        r"\\begin\{eqnarray\*?\}(.*?)\\end\{eqnarray\*?\}",
    ]

    # Section header patterns
    SECTION_PATTERNS = [
        r"^#{1,6}\s+(.*?)$",  # Markdown headers
        r"^(?:\d+\.?\s+)([A-Z].*?)$",  # Numbered sections
        r"\\(?:sub)*section\*?\{(.*?)\}",  # LaTeX sections
    ]

    def extract_knowledge(self, text: str, topic: str = "") -> dict[str, Any]:
        """Extract structured knowledge from text.

        Returns:
            {
                equations: List[str] — LaTeX equations found
                definitions: List[str] — definitions/claims
                theorems: List[str] — theorems/lemmas/propositions
                key_points: List[str] — important statements
                concepts: List[str] — mathematical/scientific concepts mentioned
                sections: List[str] — section headers found
            }
        """
        equations = self._extract_equations(text)
        definitions = self._extract_definitions(text)
        theorems = self._extract_theorems(text)
        key_points = self._extract_key_points(text, topic)
        concepts = self._extract_concepts(text)
        sections = self._extract_sections(text)

        return {
            "equations": equations,
            "definitions": definitions,
            "theorems": theorems,
            "key_points": key_points,
            "concepts": concepts,
            "sections": sections,
        }

    def _extract_equations(self, text: str) -> list[str]:
        """Extract LaTeX equations from text."""
        equations = []
        for pattern in self.EQUATION_PATTERNS:
            for match in re.finditer(pattern, text, re.DOTALL):
                eq = match.group(1).strip()
                if eq and len(eq) > 2 and len(eq) < 500:
                    # Clean up whitespace
                    eq = re.sub(r"\s+", " ", eq)
                    equations.append(eq)
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique = []
        for eq in equations:
            if eq not in seen:
                seen.add(eq)
                unique.append(eq)
        return unique[:50]  # Cap at 50 equations

    def _extract_definitions(self, text: str) -> list[str]:
        """Extract definitions from text."""
        definitions = []
        for pattern in self.DEFINITION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                defn = match.group(0).strip()
                if len(defn) > 10 and len(defn) < 500:
                    definitions.append(defn)
        return definitions[:20]

    def _extract_theorems(self, text: str) -> list[str]:
        """Extract theorems, lemmas, propositions from text."""
        theorems = []
        for pattern in self.THEOREM_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
                thm = match.group(0).strip()
                if len(thm) > 5 and len(thm) < 1000:
                    theorems.append(thm)
        return theorems[:20]

    def _extract_key_points(self, text: str, topic: str) -> list[str]:
        """Extract key points — sentences that seem important."""
        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        key_points = []

        importance_signals = [
            "important",
            "key",
            "fundamental",
            "crucial",
            "essential",
            "note that",
            "observe",
            "remark",
            "result",
            "consequence",
            "follows that",
            "implies",
            "therefore",
            "thus",
            "hence",
            "we show",
            "we prove",
            "we derive",
            "main result",
            "in particular",
            "specifically",
            "notably",
        ]

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 30 or len(sentence) > 500:
                continue
            # Check for importance signals
            lower = sentence.lower()
            if any(signal in lower for signal in importance_signals):
                key_points.append(sentence)
            # Check if it contains the topic
            elif topic and topic.lower() in lower and len(sentence) > 50:
                key_points.append(sentence)

        return key_points[:30]

    def _extract_concepts(self, text: str) -> list[str]:
        """Extract mathematical/scientific concept names from text."""
        # Known math/physics concept patterns
        concept_patterns = [
            # Capitalized multi-word terms (likely concepts)
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
            # "X of Y" patterns common in math
            r"\b((?:eigenvalue|eigenvector|eigenfunction|determinant|trace|kernel|"
            r"manifold|topology|homomorphism|isomorphism|bijection|injection|surjection|"
            r"integral|derivative|limit|convergence|divergence|continuity|"
            r"Hamiltonian|Lagrangian|Hermitian|unitary|orthogonal|symmetric|"
            r"Hilbert\s+space|Banach\s+space|vector\s+space|inner\s+product|"
            r"differential\s+equation|partial\s+differential|boundary\s+condition|"
            r"wave\s+function|partition\s+function|structure\s+function|"
            r"Green.s\s+function|Fourier\s+transform|Laplace\s+transform"
            r")(?:\s+of\s+\w+)?)\b",
        ]

        concepts: set[str] = set()
        for pattern in concept_patterns:
            for match in re.finditer(pattern, text):
                concept = match.group(1).strip()
                if len(concept) > 3:
                    concepts.add(concept)

        return sorted(concepts)[:50]

    def _extract_sections(self, text: str) -> list[str]:
        """Extract section headers from text."""
        sections = []
        for pattern in self.SECTION_PATTERNS:
            for match in re.finditer(pattern, text, re.MULTILINE):
                header = match.group(1).strip()
                if len(header) > 2 and len(header) < 100:
                    sections.append(header)
        return sections[:30]
