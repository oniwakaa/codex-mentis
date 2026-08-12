from pathlib import Path

VERSION = "0.1.0"
APP_NAME = "pitagora"

# Single source of truth for all on-disk paths. Every module must import from
# here instead of hardcoding ~/.pitagora/ string literals.
CONFIG_DIR = Path("~/.pitagora").expanduser()
DB_DIR = CONFIG_DIR / "db"
SESSIONS_DIR = CONFIG_DIR / "sessions"
JOURNEYS_DIR = CONFIG_DIR / "journeys"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
MEMORY_DB = DB_DIR / "memory.db"
KNOWLEDGE_GRAPH_DB = DB_DIR / "knowledge_graph.db"

DIFFICULTY_LEVELS = {
    1: "Novice",
    2: "Intermediate",
    3: "Advanced",
    4: "Expert",
    5: "Master"
}

SUPPORTED_FORMATS = [".pdf", ".md", ".tex", ".txt", ".yaml", ".yml"]

DEFAULT_CONCEPTS = {
    "algebra": [
        "Groups", "Rings", "Fields", "Vector Spaces", "Galois Theory"
    ],
    "calculus": [
        "Limits", "Derivatives", "Integrals", "Sequences and Series", "Multivariable Calculus"
    ],
    "linear_algebra": [
        "Matrices", "Determinants", "Eigenvalues and Eigenvectors", "Inner Product Spaces", "Linear Transformations"
    ],
    "mechanics": [
        "Kinematics", "Newton's Laws", "Lagrangian Mechanics", "Hamiltonian Mechanics", "Central Forces"
    ],
    "electromagnetism": [
        "Electrostatics", "Magnetostatics", "Maxwell's Equations", "Electromagnetic Waves", "Gauge Theory"
    ],
    "quantum": [
        "Wave Function", "Schrödinger Equation", "Quantum Operators", "Spin and Angular Momentum", "Perturbation Theory"
    ],
    "thermodynamics": [
        "Laws of Thermodynamics", "Entropy", "Statistical Ensembles", "Partition Function", "Phase Transitions"
    ],
    "topology": [
        "Metric Spaces", "Topological Spaces", "Compactness", "Connectedness", "Homotopy"
    ],
    "probability": [
        "Random Variables", "Probability Distributions", "Central Limit Theorem", "Markov Chains", "Bayesian Inference"
    ],
    "statistics": [
        "Hypothesis Testing", "Estimation Theory", "Regression Analysis", "Maximum Likelihood"
    ],
    "differential_equations": [
        "Ordinary Differential Equations", "Partial Differential Equations", "Fourier Analysis", "Green's Functions"
    ],
    "complex_analysis": [
        "Analytic Functions", "Contour Integration", "Cauchy's Theorem", "Residue Theorem", "Laurent Series"
    ]
}
