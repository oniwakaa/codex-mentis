"""PlotArchitectAgent: autonomous visual plotting sub-agent for Pitagora.

Computes precise numeric arrays (numpy/scipy) for physics and math concepts
(e.g., probability densities, quantum harmonic oscillator, dispersion relations,
potential wells, wave packets) and structures high-definition plot payloads.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from pitagora.agents.base import BaseAgent
from pitagora.agents.providers.base import BaseProvider


PLOT_ARCHITECT_SYSTEM_PROMPT = """<role>Visual Plotting Sub-Agent (PlotArchitect) for Pitagora.</role>

<purpose>
You are a specialized sub-agent for spatial, mathematical, and physical visualization.
You are invoked ONLY when a concept fundamentally benefits from spatial or geometric representation
(e.g. probability densities, potential wells, dispersion relations, wave packets, Fourier spectra).
</purpose>

<instructions>
1. Evaluate if a concept requires spatial visualization.
2. Formulate domain bounds [x_min, x_max] and compute numerical series with numpy/scipy accuracy.
3. Provide pedagogical parameter toggles (e.g., quantum numbers n=0,1,2,3 or potential toggles).
4. Output structured plot payload specifications.
</instructions>
"""

# Spatial trigger keywords where visualization is fundamentally beneficial
SPATIAL_TRIGGER_KEYWORDS = {
    "probability density",
    "wavefunction",
    "wave function",
    "potential well",
    "harmonic oscillator",
    "dispersion relation",
    "wave packet",
    "schrodinger",
    "schrödinger",
    "fourier spectrum",
    "phase portrait",
    "vector field",
    "band structure",
    "interference pattern",
    "standing wave",
    "hydrogen atom",
    "electric field",
    "magnetic field",
    "lorentz",
    "density of states",
    "gaussian distribution",
}

# Trivial concepts that should NOT trigger full plot generation
TRIVIAL_NON_PLOT_KEYWORDS = {
    "arithmetic",
    "definition of",
    "history of",
    "unit conversion",
    "scalar constant",
}


class PlotArchitectAgent(BaseAgent):
    """Sub-agent responsible for mathematical visualization decision & numeric payload generation."""

    def __init__(self, provider: BaseProvider):
        super().__init__(
            name="PlotArchitect",
            role="Visual Plotting Sub-Agent",
            provider=provider,
            system_prompt=PLOT_ARCHITECT_SYSTEM_PROMPT,
        )

    @staticmethod
    def should_visualize(text: str) -> bool:
        """Heuristic check whether query fundamentally benefits from spatial/numeric plotting."""
        t = text.lower()
        if any(bad in t for bad in TRIVIAL_NON_PLOT_KEYWORDS):
            return False
        return any(k in t for k in SPATIAL_TRIGGER_KEYWORDS) or ("plot" in t and "function" in t)

    def generate_plot_payload(
        self,
        concept: str,
        quantum_n: int = 0,
        x_range: tuple[float, float] | None = None,
        points: int = 150,
    ) -> dict[str, Any]:
        """Compute high-precision numeric arrays and return structured plot payload."""
        c = concept.lower()

        # 1. Quantum Harmonic Oscillator
        if "harmonic oscillator" in c or "quantum_ho" in c or "ho" in c or "hermite" in c:
            x_min, x_max = x_range or (-5.0, 5.0)
            x = np.linspace(x_min, x_max, points)
            psi, density, V = self._compute_quantum_ho(x, quantum_n)
            energy = quantum_n + 0.5

            return {
                "title": f"Quantum Harmonic Oscillator: State n={quantum_n} (E={energy:.1f} ħω)",
                "plot_type": "line",
                "x_label": "Position x [dimensionless]",
                "y_label": "Amplitude / Probability Density",
                "math_formula": r"\psi_n(x) = \frac{1}{\sqrt{2^n n! \sqrt{\pi}}} e^{-x^2/2} H_n(x)",
                "quantum_n": quantum_n,
                "domain": [float(x_min), float(x_max)],
                "parameters": {
                    "available_states": [0, 1, 2, 3],
                    "current_state": quantum_n,
                    "has_potential": True,
                },
                "series": [
                    {
                        "name": f"|ψ_{quantum_n}(x)|² (Prob. Density)",
                        "x": x.tolist(),
                        "y": density.tolist(),
                        "color": "#7dcfff",  # Cyan
                    },
                    {
                        "name": f"ψ_{quantum_n}(x) (Wavefunction)",
                        "x": x.tolist(),
                        "y": psi.tolist(),
                        "color": "#bb9af7",  # Purple
                    },
                    {
                        "name": "V(x) = ½x² (Potential)",
                        "x": x.tolist(),
                        "y": (0.1 * V).tolist(),
                        "color": "#e0af68",  # Amber/Yellow
                    },
                ],
            }

        # 2. Infinite Square Well / Particle in a Box
        if "infinite" in c or "square well" in c or "box" in c:
            L = 1.0
            x_min, x_max = x_range or (0.0, L)
            x = np.linspace(x_min, x_max, points)
            n_val = max(1, quantum_n if quantum_n > 0 else 1)
            psi = np.sqrt(2.0 / L) * np.sin(n_val * np.pi * x / L)
            density = psi**2

            return {
                "title": f"Particle in a Box (Infinite Well): n={n_val}",
                "plot_type": "line",
                "x_label": "Position x / L",
                "y_label": "Probability Density |ψ(x)|²",
                "math_formula": r"\psi_n(x) = \sqrt{\frac{2}{L}} \sin\left(\frac{n \pi x}{L}\right)",
                "quantum_n": n_val,
                "domain": [float(x_min), float(x_max)],
                "parameters": {
                    "available_states": [1, 2, 3, 4],
                    "current_state": n_val,
                    "has_potential": False,
                },
                "series": [
                    {
                        "name": f"|ψ_{n_val}(x)|² (Density)",
                        "x": x.tolist(),
                        "y": density.tolist(),
                        "color": "#7dcfff",
                    },
                    {
                        "name": f"ψ_{n_val}(x) (Wavefunction)",
                        "x": x.tolist(),
                        "y": psi.tolist(),
                        "color": "#bb9af7",
                    },
                ],
            }

        # 3. Dispersion Relation (e.g. Free particle or Relativistic)
        if "dispersion" in c or "band" in c or "k-space" in c:
            x_min, x_max = x_range or (-3.0, 3.0)
            k = np.linspace(x_min, x_max, points)
            omega_free = 0.5 * k**2
            omega_rel = np.sqrt(1.0 + k**2)

            return {
                "title": "Dispersion Relations: ω(k)",
                "plot_type": "line",
                "x_label": "Wavenumber k [1/m]",
                "y_label": "Frequency ω(k) / Energy E",
                "math_formula": r"\omega_{free} = \frac{\hbar k^2}{2m}, \quad E_{rel} = \sqrt{m_0^2 c^4 + p^2 c^2}",
                "domain": [float(x_min), float(x_max)],
                "parameters": {"has_potential": False},
                "series": [
                    {
                        "name": "Non-relativistic (Quadratic: ~k²)",
                        "x": k.tolist(),
                        "y": omega_free.tolist(),
                        "color": "#7aa2f7",  # Blue
                    },
                    {
                        "name": "Relativistic (Dirac/Klein-Gordon: √(1+k²))",
                        "x": k.tolist(),
                        "y": omega_rel.tolist(),
                        "color": "#7dcfff",  # Cyan
                    },
                ],
            }

        # 4. Wave packet localization
        x_min, x_max = x_range or (-6.0, 6.0)
        x = np.linspace(x_min, x_max, points)
        sigma = 1.2
        k0 = 2.5
        env = np.exp(-(x**2) / (2 * sigma**2))
        wave = env * np.cos(k0 * x)
        density = env**2

        return {
            "title": f"Gaussian Wave Packet Localization (σ={sigma})",
            "plot_type": "line",
            "x_label": "Position x",
            "y_label": "Amplitude",
            "math_formula": r"\psi(x) = e^{-x^2/(2\sigma^2)} \cos(k_0 x)",
            "domain": [float(x_min), float(x_max)],
            "parameters": {"has_potential": False},
            "series": [
                {
                    "name": "|ψ(x)|² (Probability Envelope)",
                    "x": x.tolist(),
                    "y": density.tolist(),
                    "color": "#9ece6a",  # Green
                },
                {
                    "name": "Re[ψ(x)] (Wave Packet)",
                    "x": x.tolist(),
                    "y": wave.tolist(),
                    "color": "#7dcfff",  # Cyan
                },
            ],
        }

    def _compute_quantum_ho(
        self, x: np.ndarray, n: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute exact normalized Hermite wavefunction, probability density, and harmonic potential."""
        if n == 0:
            H = np.ones_like(x)
        elif n == 1:
            H = 2 * x
        elif n == 2:
            H = 4 * x**2 - 2
        elif n == 3:
            H = 8 * x**3 - 12 * x
        elif n == 4:
            H = 16 * x**4 - 48 * x**2 + 12
        else:
            coeff = [0] * n + [1]
            H = np.polynomial.hermite.hermval(x, coeff)

        norm = 1.0 / math.sqrt((2**n) * math.factorial(n) * math.sqrt(math.pi))
        psi = norm * np.exp(-(x**2) / 2.0) * H
        density = psi**2
        V = 0.5 * x**2
        return psi, density, V
