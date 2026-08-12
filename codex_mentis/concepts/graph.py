import os
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from difflib import SequenceMatcher

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
        YAML format: domain → list of {id, name, prerequisites, ...}
        We flatten this into: graph[concept_id] = {name, prerequisites, domain, ...}
        """
        if not os.path.exists(self.yaml_path):
            self._create_seed_graph()
            return

        if YAML_AVAILABLE:
            try:
                with open(self.yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                
                if not isinstance(data, dict):
                    self._create_seed_graph()
                    return

                # Flatten domain-grouped YAML into flat concept dict
                self.graph = {}
                for domain, concepts in data.items():
                    if isinstance(concepts, list):
                        for concept in concepts:
                            if isinstance(concept, dict) and "id" in concept:
                                cid = concept["id"]
                                self.graph[cid] = {
                                    "name": concept.get("name", cid),
                                    "prerequisites": concept.get("prerequisites", []),
                                    "domain": domain,
                                    "description": concept.get("description", ""),
                                    "difficulty": concept.get("difficulty", 1),
                                    "estimated_learning_time": concept.get("estimated_learning_time", 60),
                                }
                    elif isinstance(concepts, dict):
                        # Already flat format
                        self.graph[domain] = concepts

            except Exception:
                self._create_seed_graph()
        else:
            self._parse_yaml_fallback()

        self._sync_bidirectional()

    def _sync_bidirectional(self):
        """
        Ensures all concepts have prerequisites and dependents list populated and synchronized.
        """
        # Ensure base structure
        for name, details in self.graph.items():
            if "prerequisites" not in details or not isinstance(details["prerequisites"], list):
                details["prerequisites"] = []
            if "dependents" not in details or not isinstance(details["dependents"], list):
                details["dependents"] = []
            if "difficulty" not in details:
                details["difficulty"] = 1
            if "estimated_learning_time" not in details:
                details["estimated_learning_time"] = 60
            if "domain" not in details:
                details["domain"] = "General"

        # Populate dependents from prerequisites
        for name, details in self.graph.items():
            for prereq in details["prerequisites"]:
                if prereq in self.graph:
                    if name not in self.graph[prereq]["dependents"]:
                        self.graph[prereq]["dependents"].append(name)

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
                        if "prerequisites:" in line_stripped:
                            self.graph[current_concept]["prerequisites"] = []
                        elif line_stripped.startswith("-") and "prerequisites" in self.graph[current_concept]:
                            prereq = line_stripped.replace("-", "").strip().strip('"').strip("'")
                            self.graph[current_concept]["prerequisites"].append(prereq)
                        elif ":" in line_stripped:
                            parts = line_stripped.split(":", 1)
                            key = parts[0].strip()
                            val = parts[1].strip().strip('"').strip("'")
                            if key in ("difficulty", "estimated_learning_time"):
                                try:
                                    self.graph[current_concept][key] = int(val)
                                except ValueError:
                                    self.graph[current_concept][key] = val
                            else:
                                self.graph[current_concept][key] = val
                    else:
                        if line_stripped.endswith(":"):
                            current_concept = line_stripped[:-1].strip().strip('"').strip("'")
                            self.graph[current_concept] = {"prerequisites": [], "dependents": []}
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
                "dependents": [],
                "domain": "Mathematics",
                "difficulty": 1,
                "estimated_learning_time": 60
            },
            "Calculus": {
                "description": "Limits, derivatives, integrals, and series.",
                "prerequisites": ["Algebra"],
                "dependents": [],
                "domain": "Mathematics",
                "difficulty": 3,
                "estimated_learning_time": 180
            },
            "Linear Algebra": {
                "description": "Vectors, matrices, linear transformations, and eigenvalues.",
                "prerequisites": ["Algebra"],
                "dependents": [],
                "domain": "Mathematics",
                "difficulty": 2,
                "estimated_learning_time": 120
            },
            "Classical Mechanics": {
                "description": "Newtonian dynamics, Lagrangian and Hamiltonian mechanics.",
                "prerequisites": ["Calculus", "Linear Algebra"],
                "dependents": [],
                "domain": "Physics",
                "difficulty": 4,
                "estimated_learning_time": 240
            },
            "Electromagnetism": {
                "description": "Maxwell's equations, electrostatic forces, and radiation.",
                "prerequisites": ["Calculus", "Linear Algebra"],
                "dependents": [],
                "domain": "Physics",
                "difficulty": 4,
                "estimated_learning_time": 200
            },
            "Quantum Mechanics": {
                "description": "Schrodinger equation, wavefunctions, and operators.",
                "prerequisites": ["Linear Algebra", "Calculus", "Classical Mechanics"],
                "dependents": [],
                "domain": "Physics",
                "difficulty": 5,
                "estimated_learning_time": 300
            }
        }
        self._sync_bidirectional()
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
            try:
                with open(self.yaml_path, "w", encoding="utf-8") as f:
                    for concept, details in self.graph.items():
                        f.write(f"{concept}:\n")
                        f.write(f"  description: \"{details.get('description', '')}\"\n")
                        f.write(f"  domain: \"{details.get('domain', '')}\"\n")
                        f.write(f"  difficulty: {details.get('difficulty', 1)}\n")
                        f.write(f"  estimated_learning_time: {details.get('estimated_learning_time', 60)}\n")
                        f.write("  prerequisites:\n")
                        for prereq in details.get("prerequisites", []):
                            f.write(f"    - \"{prereq}\"\n")
                        f.write("  dependents:\n")
                        for dep in details.get("dependents", []):
                            f.write(f"    - \"{dep}\"\n")
            except Exception:
                pass

    def _resolve_concept(self, name_or_id: str) -> Optional[str]:
        """Resolve a concept by name or ID. Returns the graph key or None."""
        # Direct key match
        if name_or_id in self.graph:
            return name_or_id
        # Case-insensitive name match
        lower = name_or_id.lower()
        for cid, details in self.graph.items():
            if details.get("name", "").lower() == lower:
                return cid
            if cid.lower() == lower:
                return cid
        # Partial match (name contains query or query contains name)
        for cid, details in self.graph.items():
            name = details.get("name", "").lower()
            if lower in name or name in lower:
                return cid
            if lower in cid.lower():
                return cid
        # Domain match — prefer longest domain match
        best_match = None
        best_len = 0
        for cid, details in self.graph.items():
            domain = details.get("domain", "").lower()
            if domain and (lower == domain or lower in domain or domain in lower):
                if len(domain) > best_len:
                    best_match = cid
                    best_len = len(domain)
        if best_match:
            return best_match
        return None

    def get_prerequisites(self, concept: str) -> List[str]:
        """
        Returns the list of direct prerequisites of a concept.
        Accepts concept name or ID.
        """
        cid = self._resolve_concept(concept)
        if cid:
            prereq_ids = self.graph.get(cid, {}).get("prerequisites", [])
            # Return names, not IDs
            return [self.graph.get(p, {}).get("name", p) for p in prereq_ids if p in self.graph]
        return []

    def get_dependents(self, concept: str) -> List[str]:
        """
        Returns the concepts that require the given concept as a prerequisite.
        """
        cid = self._resolve_concept(concept)
        return self.graph.get(cid, {}).get("dependents", []) if cid else []

    def get_learning_path(self, target: str) -> List[str]:
        """
        Computes a topologically sorted list of concepts needed to understand the target.
        """
        cid = self._resolve_concept(target)
        if not cid:
            return []
        
        visited: Set[str] = set()
        path: List[str] = []

        def dfs(node: str):
            if node in visited:
                return
            visited.add(node)
            for prereq in self.graph.get(node, {}).get("prerequisites", []):
                if prereq in self.graph:
                    dfs(prereq)
            name = self.graph.get(node, {}).get("name", node)
            path.append(name)

        dfs(cid)
        return path

    def get_optimized_path(self, target: str, mastered_concepts: Optional[List[str]] = None) -> List[str]:
        """
        Computes an optimized learning path to master a target concept, sorting available
        nodes dynamically by difficulty and estimated learning time (e.g. build up from easiest).
        """
        mastered = set(mastered_concepts or [])
        needed = set(self.get_learning_path(target)) - mastered
        
        if not needed:
            return []
            
        path = []
        visited = set()
        
        while len(path) < len(needed):
            # Find all nodes in `needed` that are not yet in `path`
            # and whose prerequisites are either mastered or already in `path`
            available = []
            for node in needed:
                if node in visited:
                    continue
                prereqs = set(self.get_prerequisites(node))
                if prereqs.issubset(mastered.union(visited)):
                    available.append(node)
                    
            if not available:
                # Should not happen in a DAG, but fallback to prevent infinite loop
                break
                
            # Sort available concepts by difficulty (ascending) and learning time (ascending)
            available.sort(key=lambda x: (
                self.graph[x].get("difficulty", 1),
                self.graph[x].get("estimated_learning_time", 60)
            ))
            
            # Select the optimized next concept
            next_concept = available[0]
            path.append(next_concept)
            visited.add(next_concept)
            
        return path

    def add_concept(
        self, 
        concept: str, 
        prerequisites: List[str], 
        description: str = "", 
        domain: str = "",
        difficulty: int = 1,
        estimated_learning_time: int = 60
    ):
        """
        Adds a new concept and updates bidirectional relations, then persists the graph.
        """
        self.graph[concept] = {
            "description": description,
            "prerequisites": prerequisites,
            "dependents": [],
            "domain": domain,
            "difficulty": difficulty,
            "estimated_learning_time": estimated_learning_time
        }
        self._sync_bidirectional()
        self.save()

    def get_clusters_by_domain(self) -> Dict[str, List[str]]:
        """
        Clusters concepts by their domain.
        """
        clusters = {}
        for concept, details in self.graph.items():
            domain = details.get("domain", "General")
            if domain not in clusters:
                clusters[domain] = []
            clusters[domain].append(concept)
        return clusters

    def search_concepts(self, query: str, threshold: float = 0.4) -> List[Tuple[str, float]]:
        """
        Fuzzy matches concept names and descriptions to rank them by relevance.
        """
        results = []
        for name, details in self.graph.items():
            # Check name similarity
            name_score = SequenceMatcher(None, query.lower(), name.lower()).ratio()
            
            # Check description similarity
            desc = details.get("description", "")
            desc_score = 0.0
            if desc:
                # Simple substring check boost
                if query.lower() in desc.lower():
                    desc_score = 0.5
                else:
                    desc_score = max(SequenceMatcher(None, query.lower(), word.lower()).ratio() for word in desc.split()) * 0.4
                    
            combined_score = max(name_score, desc_score)
            if combined_score >= threshold:
                results.append((name, combined_score))
                
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def export_to_json(self, dest_path: str):
        """Exports the graph structure to a JSON file."""
        dest_path = os.path.expanduser(dest_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(self.graph, f, indent=2)

    def export_to_dot(self, dest_path: str):
        """Exports the graph structure to a Graphviz DOT file."""
        dest_path = os.path.expanduser(dest_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        lines = ["digraph ConceptGraph {", "    rankdir=LR;", "    node [shape=box, style=filled, color=lightblue];"]
        
        # Write node attributes
        for name, details in self.graph.items():
            difficulty = details.get("difficulty", 1)
            domain = details.get("domain", "General")
            label = f"{name}\\nDomain: {domain}\\nDiff: {difficulty}"
            lines.append(f"    \"{name}\" [label=\"{label}\"];")
            
        # Write edges
        for name, details in self.graph.items():
            for prereq in details.get("prerequisites", []):
                lines.append(f"    \"{prereq}\" -> \"{name}\";")
                
        lines.append("}")
        
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def visualize(self, concept: str) -> str:
        """
        Returns an ASCII tree displaying prerequisites recursively.
        """
        lines = []

        def build_tree(node: str, prefix: str = "", is_last: bool = True):
            details = self.graph.get(node, {})
            desc = details.get("description", "")
            diff = details.get("difficulty", 1)
            desc_str = f" ({desc[:35]}... | Diff: {diff})" if desc else f" (Diff: {diff})"
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
