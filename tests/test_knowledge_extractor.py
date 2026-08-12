import pytest
from pitagora.knowledge.extractor import KnowledgeExtractor

def test_knowledge_extractor_with_real_math():
    extractor = KnowledgeExtractor()
    
    math_paper_text = """
# Quantum Mechanics Basics
This is an introduction to wave mechanics.

## Section 1: The Wave Function
We define the state of a quantum particle as a wave function. Let $\\Psi(x, t)$ be the wave function of the particle in a one-dimensional space.
The probability density is defined as the absolute square of the wave function:
$$P(x, t) = |\\Psi(x, t)|^2$$

Theorem: The wave function must be normalized. This means that:
\\begin{equation}
\\int_{-\\infty}^{\\infty} |\\Psi(x, t)|^2 dx = 1
\\end{equation}

This is a fundamental postulate of quantum mechanics. Specifically, it implies that the particle must exist somewhere in the universe. Note that we must also satisfy boundary conditions.

A wave function is defined as a complex-valued function in a Hilbert space.

Let us evaluate the Hamiltonian operator on the state. The Hamiltonian of the system is the sum of kinetic and potential energies:
\\begin{align}
\\hat{H} = -\\frac{\\hbar^2}{2m} \\frac{d^2}{dx^2} + V(x)
\\end{align}
    """
    
    extracted = extractor.extract_knowledge(math_paper_text, topic="wave function")
    
    # 1. Equations
    eqs = extracted["equations"]
    assert any("P(x, t) = |\\Psi(x, t)|^2" in eq for eq in eqs)
    assert any("\\int_{-\\infty}^{\\infty} |\\Psi(x, t)|^2 dx = 1" in eq for eq in eqs)
    assert any("\\hat{H} = -\\frac{\\hbar^2}{2m}" in eq for eq in eqs)
    
    # 2. Definitions
    defs = extracted["definitions"]
    assert any("We define" in d for d in defs)
    
    # 3. Theorems
    thms = extracted["theorems"]
    assert any("Theorem: The wave function must be normalized." in t for t in thms)
    
    # 4. Key points
    kp = extracted["key_points"]
    assert any("fundamental postulate" in p for p in kp)
    assert any("implies" in p for p in kp)
    
    # 5. Concepts
    concepts = extracted["concepts"]
    assert any("Hilbert space" in c for c in concepts)
    assert any("wave function" in c.lower() for c in concepts)
    assert any("Hamiltonian" in c for c in concepts)
    
    # 6. Sections
    secs = extracted["sections"]
    assert "Quantum Mechanics Basics" in secs
    assert "Section 1: The Wave Function" in secs
