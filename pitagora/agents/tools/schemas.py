"""Schema definitions for agent tools."""

from typing import Any

RENDER_TERMINAL_PLOT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "render_terminal_plot",
        "description": (
            "Render an interactive 2D scientific plot or visualization directly in the terminal/TUI. "
            "MUST be invoked whenever explaining physical phenomena, wavefunctions, potentials, "
            "harmonic oscillators, probability densities, or mathematical functions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Descriptive title for the plot (e.g. 'Quantum Harmonic Oscillator: n=1 |ψ(x)|²')",
                },
                "plot_type": {
                    "type": "string",
                    "enum": ["line", "scatter", "bar"],
                    "description": "Chart style: line, scatter, or bar",
                },
                "x_label": {
                    "type": "string",
                    "description": "Label for the horizontal x-axis (e.g. 'Position x (m)')",
                },
                "y_label": {
                    "type": "string",
                    "description": "Label for the vertical y-axis (e.g. 'Probability Density |ψ(x)|²')",
                },
                "series": {
                    "type": "array",
                    "description": "One or more data series to plot",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Legend label for this curve",
                            },
                            "x": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "List of numeric x coordinates",
                            },
                            "y": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "List of numeric y coordinates",
                            },
                            "marker": {
                                "type": "string",
                                "description": "Optional marker glyph or style",
                            },
                        },
                        "required": ["name", "x", "y"],
                    },
                },
                "math_formula": {
                    "type": "string",
                    "description": "Optional mathematical expression/definition (e.g. 'y = exp(-x^2/2)')",
                },
                "quantum_n": {
                    "type": "integer",
                    "description": "Optional quantum number / state index (e.g. 0, 1, 2, 3)",
                },
                "domain": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Optional [x_min, x_max] domain bounds",
                },
                "parameters": {
                    "type": "object",
                    "description": "Optional interactive parameter descriptors (e.g. available states, toggle potential)",
                },
            },
            "required": ["title", "plot_type", "x_label", "y_label", "series"],
        },
    },
}

ALL_AGENT_TOOLS = [RENDER_TERMINAL_PLOT_TOOL]
