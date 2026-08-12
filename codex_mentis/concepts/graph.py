import os
from typing import Dict, Any, List, Optional, Set

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

class ConceptGraph:
    def __init__(self, yaml_path: Optional[str] = None):
        """
        Manages the DAG of math and physics concepts.
        """
        self.yaml_path = yaml_path
        if not self.yaml_path:
            # Default packaged location
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.yaml_path = os.path.join(base_dir, "data", "concepts.yaml")

        self.graph: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self):
        """
        Loads the concept DAG from concepts.yaml.
        """
        if not os.path.exists(self.yaml_path):
            # Seed default concepts if concepts.yaml doesn't exist
            self._create_seed_graph()
            return

        if YAML_AVAILABLE:
            try:
                with open(self.yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    self.graph = data if isinstance(data, dict) else {}
            except Exception:
                self._create_seed_graph()
        else:
            # Simple line parser fallback for YAML if PyYAML is missing
            self._parse_yaml_fallback()

    def _parse_yaml_fallback(self):
        """
        Simple fallback parser for reading concepts.yaml.
        """
        self.graph = {}
        current_concept = None
        try:
            with open(self.yaml_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_stripped = line.strip()
                    if not line_stripped or line_stripped.startswith("#"):
                        continue
                    if line.startswith("  ") and current_concept:
                        # Inside concept keys
                        if "prerequisites:" in line_stripped:
                            self.graph[current_concept]["prerequisites"] = []
                        elif line_stripped.startswith("-") and "prerequisites" in self.graph[current_concept]:
                            prereq = line_stripped.replace("-", "").strip().strip('"').strip("'")
                            self.graph[current_concept]["prerequisites"].append(prereq)
                        elif ":" in line_stripped:
                            parts = line_stripped.split(":", 1)
                            key = parts[0].strip()
                            val = parts[1].strip().strip('"').strip("'")
                            self.graph[current_concept][key] = val
                    else:
                        # New concept root key
                        if line_stripped.endswith(":"):
                            current_concept = line_stripped[:-1].strip().strip('"').strip("'")
                            self.graph[current_concept] = {"prerequisites": []}
        except Exception:
            self._create_seed_graph()

    def _create_seed_graph(self):
        """
        Initializes a default seed graph for mathematics and physics.
        """
        self.graph = {
            "Algebra": {
                "description": "Basic arithmetic, equations, variables.",
                "prerequisites": [],
                "domain": "Mathematics"
            },
            "Calculus": {
                "description": "Limits, derivatives, integrals, and series.",
                "prerequisites": ["Algebra"],
                "domain": "Mathematics"
            },
            "Linear Algebra": {
                "description": "Vectors, matrices, linear transformations, and eigenvalues.",
                "prerequisites": ["Algebra"],
                "domain": "Mathematics"
            },
            "Classical Mechanics": {
                "description": "Newtonian dynamics, Lagrangian and Hamiltonian mechanics.",
                "prerequisites": ["Calculus", "Linear Algebra"],
                "domain": "Physics"
            },
            "Electromagnetism": {
                "description": "Maxwell's equations, electrostatic forces, and radiation.",
                "prerequisites": ["Calculus", "Linear Algebra"],
                "domain": "Physics"
            },
            "Quantum Mechanics": {
                "description": "Schrodinger equation, wavefunctions, and operators.",
                "prerequisites": ["Linear Algebra", "Calculus", "Classical Mechanics"],
                "domain": "Physics"
            }
        }
        self.save()

    def save(self):
        """
        Saves the concept graph back to YAML.
        """
        os.makedirs(os.path.dirname(self.yaml_path), exist_ok=True)
        if YAML_AVAILABLE:
            try:
                with open(self.yaml_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(self.graph, f, default_flow_style=False, sort_keys=False)
            except Exception:
                pass
        else:
            # Fallback simple writer
            try:
                with open(self.yaml_path, "w", encoding="utf-8") as f:
                    for concept, details in self.graph.items():
                        f.write(f"{concept}:\n")
                        f.write(f"  description: \"{details.get('description', '')}\"\n")
                        f.write(f"  domain: \"{details.get('domain', '')}\"\n")
                        f.write("  prerequisites:\n")
                        for prereq in details.get("prerequisites", []):
                            f.write(f"    - \"{prereq}\"\n")
            except Exception:
                pass

    def get_prerequisites(self, concept: str) -> List[str]:
        """
        Returns the list of direct prerequisites of a concept.
        """
        return self.graph.get(concept, {}).get("prerequisites", [])

    def get_dependents(self, concept: str) -> List[str]:
        """
        Returns the concepts that require the given concept as a prerequisite.
        """
        dependents = []
        for name, details in self.graph.items():
            if concept in details.get("prerequisites", []):
                dependents.append(name)
        return dependents

    def get_learning_path(self, target: str) -> List[str]:
        """
        Computes a topologically sorted list of concepts needed to understand the target.
        """
        visited: Set[str] = set()
        path: List[str] = []

        def dfs(node: str):
            if node in visited:
                return
            visited.add(node)
            for prereq in self.get_prerequisites(node):
                if prereq in self.graph:
                    dfs(prereq)
            path.append(node)

        if target in self.graph:
            dfs(target)
        return path

    def add_concept(self, concept: str, prerequisites: List[str], description: str = "", domain: str = ""):
        """
        Adds a new concept and its prerequisites to the DAG and persists it.
        """
        self.graph[concept] = {
            "description": description,
            "prerequisites": prerequisites,
            "domain": domain
        }
        self.save()

    def visualize(self, concept: str) -> str:
        """
        Returns an ASCII tree displaying prerequisites recursively.
        """
        lines = []

        def build_tree(node: str, prefix: str = "", is_last: bool = True):
            # Show description if present
            desc = self.graph.get(node, {}).get("description", "")
            desc_str = f" ({desc[:40]}...)" if desc else ""
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{node}{desc_str}")
            
            prereqs = self.get_prerequisites(node)
            new_prefix = prefix + ("    " if is_last else "│   ")
            for i, pr in enumerate(prereqs):
                if pr in self.graph:
                    build_tree(pr, new_prefix, i == len(prereqs) - 1)
                else:
                    lines.append(f"{new_prefix}└── {pr} (Prerequisite info missing)")

        if concept in self.graph:
            lines.append(f"Prerequisite tree for {concept}:")
            build_tree(concept, "", True)
        else:
            lines.append(f"Concept '{concept}' not found in concept graph.")

        return "\n".join(lines)
