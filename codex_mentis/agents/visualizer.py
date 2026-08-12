import sys
import re
import os
from io import StringIO
from typing import Dict, Any, List, Optional, Tuple
from codex_mentis.agents.base import BaseAgent, AgentResponse
from codex_mentis.agents.providers.base import BaseProvider

VISUALIZER_SYSTEM_PROMPT = """You are the Visualizer Agent for Codex Mentis. Your role is to represent mathematical and physical information visually.

Guidelines:
1. Terminal Layouts: When asked to plot, use your tools or libraries (like plotext) to generate beautiful ASCII plots.
2. Concept Relationships: Create clear, hierarchical structural maps (trees or graphs) using ASCII drawing characters (e.g., ├─, └─, ──) to show dependencies.
3. Proof Logical Paths: Structure proof steps as trees showing what hypotheses lead to which intermediate claims and final Q.E.D.
"""

class VisualizerAgent(BaseAgent):
    def __init__(self, provider: BaseProvider):
        super().__init__(
            name="Visualizer",
            role="Mathematical Visualization Specialist",
            provider=provider,
            system_prompt=VISUALIZER_SYSTEM_PROMPT
        )

    def plot_expression(
        self, 
        expr: str, 
        x_range: Tuple[float, float] = (-10.0, 10.0), 
        plot_type: str = "line",
        points: int = 100,
        save_path: Optional[str] = None
    ) -> str:
        """
        Plots a SymPy-compatible expression over the given x_range.
        Uses plotext to generate a terminal ASCII plot.
        Optionally uses matplotlib to save a figure to disk if save_path is provided.
        """
        # Parse expression and calculate data points
        x_vals = []
        y_vals = []
        
        step = (x_range[1] - x_range[0]) / (points - 1)
        
        try:
            import sympy
            from sympy.parsing.sympy_parser import parse_expr
            x_sym = sympy.Symbol('x')
            parsed_expr = parse_expr(expr)
            
            for i in range(points):
                val = x_range[0] + i * step
                x_vals.append(val)
                # Substitute and evaluate numerically
                res = parsed_expr.subs(x_sym, val).evalf()
                # Handle complex values or non-numerical answers
                if res.is_real:
                    y_vals.append(float(res))
                else:
                    y_vals.append(0.0)
        except Exception:
            # Fallback evaluation if sympy fails or is not available
            import math
            # Basic safe math evaluation environment
            safe_dict = {
                'x': 0.0,
                'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
                'exp': math.exp, 'log': math.log, 'sqrt': math.sqrt,
                'pi': math.pi, 'e': math.e, 'pow': math.pow
            }
            for i in range(points):
                val = x_range[0] + i * step
                x_vals.append(val)
                safe_dict['x'] = val
                try:
                    res = eval(expr, {"__builtins__": None}, safe_dict)
                    y_vals.append(float(res))
                except Exception:
                    y_vals.append(0.0)

        # Generate terminal plot using plotext
        terminal_plot = ""
        try:
            import plotext as plt
            plt.clear_data()
            plt.clear_terminal()
            
            if plot_type == "scatter":
                plt.scatter(x_vals, y_vals)
            else:
                plt.plot(x_vals, y_vals)
                
            plt.title(f"Plot of y = {expr}")
            plt.xlabel("x")
            plt.ylabel("y")
            
            # Capture output of show() which prints to terminal
            old_stdout = sys.stdout
            captured = sys.stdout = StringIO()
            plt.show()
            sys.stdout = old_stdout
            terminal_plot = captured.getvalue()
        except ImportError:
            # Simple fallback text plot if plotext is missing
            terminal_plot = f"[Plotext not installed. Data Summary for {expr}: Min Y={min(y_vals):.2f}, Max Y={max(y_vals):.2f}]"

        # Generate file plot if save_path is requested
        if save_path:
            try:
                import matplotlib.pyplot as plt_mp
                plt_mp.figure(figsize=(8, 5))
                plt_mp.plot(x_vals, y_vals, label=f"y = {expr}")
                plt_mp.title(f"Plot of {expr}")
                plt_mp.xlabel("x")
                plt_mp.ylabel("y")
                plt_mp.grid(True)
                plt_mp.legend()
                
                # Create parent directories if they do not exist
                os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                plt_mp.savefig(save_path)
                plt_mp.close()
                terminal_plot += f"\nSaved high-resolution plot to {save_path}"
            except ImportError:
                terminal_plot += "\n[Warning: matplotlib not installed. High-res image could not be saved.]"
            except Exception as e:
                terminal_plot += f"\n[Warning: Failed to save plot: {str(e)}]"

        return terminal_plot

    def create_concept_map(self, topic: str, connections: Optional[List[Tuple[str, str]]] = None) -> str:
        """
        Generates an ASCII representation of a concept map.
        """
        # If connections are not provided, we query LLM to describe connections first
        if not connections:
            prompt = (
                f"Identify the key sub-concepts and prerequisites for the topic '{topic}'. "
                f"Return them as a flat list of connections in format 'A -> B' (A is prerequisite of B)."
            )
            resp = self.think(prompt)
            connections = []
            for line in resp.content.splitlines():
                match = re.search(r"([\w\s\-]+)\s*->\s*([\w\s\-]+)", line)
                if match:
                    connections.append((match.group(1).strip(), match.group(2).strip()))
                    
        if not connections:
            # Fallback
            return f"Concept: {topic}\n └─ (No connections discovered)"

        # Build adjacency list
        adj: Dict[str, List[str]] = {}
        all_nodes = set()
        has_parents = set()
        for p, child in connections:
            adj.setdefault(p, []).append(child)
            all_nodes.add(p)
            all_nodes.add(child)
            has_parents.add(child)
            
        roots = all_nodes - has_parents
        if not roots:
            roots = {connections[0][0]} if connections else {topic}

        output_lines = []
        
        def render_node(node: str, prefix: str = "", is_last: bool = True):
            connector = "└── " if is_last else "├── "
            output_lines.append(f"{prefix}{connector}{node}")
            
            children = adj.get(node, [])
            new_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(children):
                render_node(child, new_prefix, i == len(children) - 1)

        output_lines.append(f"Concept Map: {topic}")
        for i, root in enumerate(sorted(roots)):
            render_node(root, "", i == len(roots) - 1)

        return "\n".join(output_lines)

    def render_proof_tree(self, proof: str) -> str:
        """
        Parses a written proof and structures it as an ASCII dependency tree.
        """
        prompt = (
            f"Given the mathematical proof:\n"
            f"--- PROOF ---\n{proof}\n-------------\n"
            f"Identify the step-by-step claims and their justifications. "
            f"Draw a logical deduction tree showing how assumptions flow to the final QED. "
            f"Use ASCII lines (├──, └──) for the visualization."
        )
        resp = self.think(prompt)
        return resp.content
