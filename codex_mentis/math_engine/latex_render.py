import re
from typing import List, Any, Union

class LatexRenderer:
    UNICODE_MAP = {
        r'\sum': '∑',
        r'\int': '∫',
        r'\sqrt': '√',
        r'\infty': '∞',
        r'\pi': 'π',
        r'\alpha': 'α',
        r'\beta': 'β',
        r'\gamma': 'γ',
        r'\delta': 'δ',
        r'\epsilon': 'ε',
        r'\zeta': 'ζ',
        r'\eta': 'η',
        r'\theta': 'θ',
        r'\iota': 'ι',
        r'\kappa': 'κ',
        r'\lambda': 'λ',
        r'\mu': 'μ',
        r'\nu': 'ν',
        r'\xi': 'ξ',
        r'\omicron': 'ο',
        r'\pi': 'π',
        r'\rho': 'ρ',
        r'\sigma': 'σ',
        r'\tau': 'τ',
        r'\upsilon': 'υ',
        r'\phi': 'φ',
        r'\chi': 'χ',
        r'\psi': 'ψ',
        r'\omega': 'ω',
        r'\partial': '∂',
        r'\nabla': '∇',
        r'\times': '×',
        r'\div': '÷',
        r'\pm': '±',
        r'\neq': '≠',
        r'\approx': '≈',
        r'\leq': '≤',
        r'\geq': '≥',
        r'\cdot': '·',
        r'\hbar': 'ℏ',
        r'\psi': 'ψ',
        r'\Psi': 'Ψ',
        r'\phi': 'φ',
        r'\Phi': 'Φ',
        r'\theta': 'θ',
        r'\Theta': 'Θ',
        r'\lambda': 'λ',
        r'\Lambda': 'Λ',
        r'\sigma': 'σ',
        r'\Sigma': 'Σ',
        r'\omega': 'ω',
        r'\Omega': 'Ω',
        r'\to': '→',
        r'\rightarrow': '→',
        r'\infty': '∞',
    }

    SUPERSCRIPTS = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
        '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
        'n': 'ⁿ', 'x': 'ˣ', 'y': 'ʸ', 'i': 'ⁱ', 'j': 'ʲ'
    }

    SUBSCRIPTS = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
        '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
        '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
        'a': 'ₐ', 'e': 'ₑ', 'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ',
        'k': 'ₖ', 'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ',
        'p': 'ₚ', 'r': 'ᵣ', 's': 'ₛ', 't': 'ₜ', 'u': 'ᵤ',
        'v': 'ᵥ', 'x': 'ₓ'
    }

    def __init__(self):
        pass

    def render_inline(self, latex: str) -> str:
        """Converts LaTeX math expression into a terminal-friendly unicode string."""
        if not latex:
            return ""
            
        rendered = latex
        
        # Replace simple fractions: \frac{a}{b} -> (a)/(b)
        rendered = re.sub(r'\\frac\s*{(.*?)}\s*{(.*?)}', r'(\1)/(\2)', rendered)
        
        # Replace LaTeX operations and Greek characters
        for l_cmd, uni_char in self.UNICODE_MAP.items():
            # Match word boundaries or escape sequence
            rendered = rendered.replace(l_cmd, uni_char)

        # Handle simple superscripts like ^{2} or ^2
        def replace_super(match):
            val = match.group(1) or match.group(2)
            return "".join(self.SUPERSCRIPTS.get(c, c) for c in val)
        rendered = re.sub(r'\^{(.*?)}|\^([0-9a-zA-Z\+\-\(\)])', replace_super, rendered)

        # Handle simple subscripts like _{0} or _0
        def replace_sub(match):
            val = match.group(1) or match.group(2)
            return "".join(self.SUBSCRIPTS.get(c, c) for c in val)
        rendered = re.sub(r'_{([a-zA-Z0-9\+\-\(\)])}|_([a-zA-Z0-9\+\-\(\)])', replace_sub, rendered)

        # Remove leftover braces and extra slashes
        rendered = re.sub(r'[{}]', '', rendered)
        rendered = rendered.replace(r'\left', '').replace(r'\right', '')
        rendered = re.sub(r'\\(mathrm|mathbf|mathit|text)', '', rendered)
        
        return rendered.strip()

    def render_equation(self, latex: str) -> str:
        """Renders an equation block centered with surrounding margins."""
        inline = self.render_inline(latex)
        # Center in terminal width (approx 80 chars)
        width = 60
        padding = (width - len(inline)) // 2
        padding = max(0, padding)
        
        box = []
        box.append("=" * width)
        box.append(" " * padding + inline)
        box.append("=" * width)
        return "\n".join(box)

    def render_matrix(self, matrix: Union[str, List[List[Any]]]) -> str:
        """Renders a matrix as a beautiful terminal ASCII block.
        
        Accepts a nested list, or a string like '[[1, 2], [3, 4]]' or LaTeX matrix representation.
        """
        grid: List[List[str]] = []
        if isinstance(matrix, str):
            # Try parsing LaTeX matrix \begin{matrix} ... \end{matrix} or [[]] format
            if 'matrix' in matrix or 'pmatrix' in matrix or 'bmatrix' in matrix:
                # Basic latex matrix parser
                body = re.search(r'\\begin{[p|b]?matrix}(.*?)\\end{[p|b]?matrix}', matrix, re.DOTALL)
                if body:
                    lines = body.group(1).strip().split(r'\\')
                    for l in lines:
                        if l.strip():
                            grid.append([self.render_inline(cell.strip()) for cell in l.split('&')])
            else:
                try:
                    # Try eval nested lists
                    parsed = eval(matrix)
                    if isinstance(parsed, list):
                        for r in parsed:
                            if isinstance(r, list):
                                grid.append([str(c) for c in r])
                            else:
                                grid.append([str(r)])
                except Exception:
                    pass
        elif isinstance(matrix, list):
            for r in matrix:
                if isinstance(r, list):
                    grid.append([str(c) for c in r])
                else:
                    grid.append([str(r)])

        if not grid:
            return str(matrix)

        # Find max width for each column
        num_cols = max(len(row) for row in grid)
        col_widths = [0] * num_cols
        for row in grid:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))

        # Render matrix brackets
        n_rows = len(grid)
        out = []
        for r_idx, row in enumerate(grid):
            # Pad cells
            row_str = "  ".join(cell.rjust(col_widths[i]) for i, cell in enumerate(row))
            
            # Left/Right bracket shapes
            if n_rows == 1:
                left, right = "[", "]"
            elif r_idx == 0:
                left, right = "┌", "┐"
            elif r_idx == n_rows - 1:
                left, right = "└", "┘"
            else:
                left, right = "│", "│"
                
            out.append(f"{left}  {row_str}  {right}")
            
        return "\n".join(out)

    def render_proof(self, steps: List[str]) -> str:
        """Formats a mathematical proof with line numbers and clean layout."""
        lines = []
        lines.append("PROOF DERIVATION:")
        lines.append("─" * 60)
        for idx, step in enumerate(steps):
            rendered_step = self.render_inline(step)
            lines.append(f"  ({idx + 1:02d})   {rendered_step}")
        lines.append("─" * 60)
        return "\n".join(lines)
