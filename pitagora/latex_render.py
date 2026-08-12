"""LaTeX to Unicode converter for terminal display."""
import re

# Greek letters
GREEK = {
    r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
    r'\epsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η', r'\theta': 'θ',
    r'\iota': 'ι', r'\kappa': 'κ', r'\lambda': 'λ', r'\mu': 'μ',
    r'\nu': 'ν', r'\xi': 'ξ', r'\pi': 'π', r'\rho': 'ρ',
    r'\sigma': 'σ', r'\tau': 'τ', r'\upsilon': 'υ', r'\phi': 'φ',
    r'\chi': 'χ', r'\psi': 'ψ', r'\omega': 'ω',
    r'\Alpha': 'Α', r'\Beta': 'Β', r'\Gamma': 'Γ', r'\Delta': 'Δ',
    r'\Theta': 'Θ', r'\Lambda': 'Λ', r'\Xi': 'Ξ', r'\Pi': 'Π',
    r'\Sigma': 'Σ', r'\Phi': 'Φ', r'\Psi': 'Ψ', r'\Omega': 'Ω',
}

# Operators and symbols
OPERATORS = {
    r'\partial': '∂', r'\nabla': '∇', r'\infty': '∞',
    r'\int': '∫', r'\iint': '∬', r'\iiint': '∭',
    r'\sum': '∑', r'\prod': '∏',
    r'\sqrt': '√', r'\pm': '±', r'\mp': '∓',
    r'\times': '×', r'\div': '÷', r'\cdot': '·',
    r'\leq': '≤', r'\geq': '≥', r'\neq': '≠', r'\approx': '≈',
    r'\equiv': '≡', r'\sim': '∼', r'\propto': '∝',
    r'\in': '∈', r'\notin': '∉', r'\subset': '⊂', r'\supset': '⊃',
    r'\cup': '∪', r'\cap': '∩', r'\emptyset': '∅',
    r'\forall': '∀', r'\exists': '∃', r'\neg': '¬',
    r'\rightarrow': '→', r'\leftarrow': '←', r'\Rightarrow': '⇒',
    r'\Leftarrow': '⇐', r'\leftrightarrow': '↔',
    r'\ldots': '…', r'\cdots': '⋯', r'\vdots': '⋮', r'\ddots': '⋱',
    r'\hbar': 'ħ', r'\ell': 'ℓ', r'\Re': 'ℜ', r'\Im': 'ℑ',
    r'\le': '≤', r'\ge': '≥', r'\ne': '≠',
    r'\to': '→', r'\mapsto': '↦',
    r'\langle': '⟨', r'\rangle': 'rangle',
    r'\left': '', r'\right': '',  # sizing commands, just remove
    r'\quad': ' ', r'\qquad': '  ', r'\,': ' ', r'\;': ' ',
    r'\!': '', r'\enspace': ' ', r'\thinspace': ' ',
}

# Superscript/subscript mappings
SUPERSCRIPTS = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'n': 'ⁿ', 'i': 'ⁱ',
}

SUBSCRIPTS = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
    'a': 'ₐ', 'e': 'ₑ', 'o': 'ₒ', 'x': 'ₓ',
}


def latex_to_unicode(text: str) -> str:
    """Convert LaTeX math notation to Unicode for terminal display."""
    # Remove display math delimiters
    text = text.replace('\\[', '').replace('\\]', '')
    text = text.replace('\\(', '').replace('\\)', '')
    
    # Convert superscripts: ^{...} or ^x
    def sup_replace(m):
        content = m.group(1) or m.group(2) or ''
        return ''.join(SUPERSCRIPTS.get(c, c) for c in content)
    text = re.sub(r'\^\{([^}]*)\}|\^(\w)', sup_replace, text)
    
    # Convert subscripts: _{...} or _x
    def sub_replace(m):
        content = m.group(1) or m.group(2) or ''
        return ''.join(SUBSCRIPTS.get(c, c) for c in content)
    text = re.sub(r'_\{([^}]*)\}|_(\w)', sub_replace, text)
    
    # Convert fractions: \frac{a}{b} → a/b
    text = re.sub(r'\\frac\{([^}]*)\}\{([^}]*)\}', r'(\1)/(\2)', text)
    
    # Convert Greek letters (longer patterns first)
    for latex, uni in sorted(GREEK.items(), key=lambda x: -len(x[0])):
        text = text.replace(latex, uni)
    
    # Convert operators (longer patterns first)
    for latex, uni in sorted(OPERATORS.items(), key=lambda x: -len(x[0])):
        text = text.replace(latex, uni)
    
    # Remove remaining backslashes from known commands
    text = re.sub(r'\\(?:text|mathrm|mathbf|mathit|mathsf|textbf|textit)\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\(?:sin|cos|tan|sec|csc|cot|log|ln|exp|lim|sup|inf|max|min|det)\b', 
                  lambda m: m.group(0).lstrip('\\'), text)
    
    # Clean up remaining LaTeX commands
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    
    # Clean up braces
    text = text.replace('{', '').replace('}', '')
    
    # Clean up spacing
    text = re.sub(r'  +', ' ', text)
    
    return text.strip()


def render_equation_box(equation: str, width: int = 60) -> str:
    """Render an equation in a nice terminal box."""
    rendered = latex_to_unicode(equation)
    lines = []
    lines.append('┌' + '─' * (width - 2) + '┐')
    # Center the equation
    padding = (width - 2 - len(rendered)) // 2
    lines.append('│' + ' ' * max(0, padding) + rendered + ' ' * max(0, width - 2 - padding - len(rendered)) + '│')
    lines.append('└' + '─' * (width - 2) + '┘')
    return '\n'.join(lines)
