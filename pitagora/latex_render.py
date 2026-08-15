"""LaTeX to Unicode converter for terminal display."""

import re

# Greek letters
GREEK = {
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\delta": "δ",
    r"\epsilon": "ε",
    r"\zeta": "ζ",
    r"\eta": "η",
    r"\theta": "θ",
    r"\iota": "ι",
    r"\kappa": "κ",
    r"\lambda": "λ",
    r"\mu": "μ",
    r"\nu": "ν",
    r"\xi": "ξ",
    r"\pi": "π",
    r"\rho": "ρ",
    r"\sigma": "σ",
    r"\tau": "τ",
    r"\upsilon": "υ",
    r"\phi": "φ",
    r"\chi": "χ",
    r"\psi": "ψ",
    r"\omega": "ω",
    r"\Alpha": "Α",
    r"\Beta": "Β",
    r"\Gamma": "Γ",
    r"\Delta": "Δ",
    r"\Theta": "Θ",
    r"\Lambda": "Λ",
    r"\Xi": "Ξ",
    r"\Pi": "Π",
    r"\Sigma": "Σ",
    r"\Phi": "Φ",
    r"\Psi": "Ψ",
    r"\Omega": "Ω",
}

# Operators and symbols
OPERATORS = {
    r"\partial": "∂",
    r"\nabla": "∇",
    r"\infty": "∞",
    r"\int": "∫",
    r"\iint": "∬",
    r"\iiint": "∭",
    r"\sum": "∑",
    r"\prod": "∏",
    r"\sqrt": "√",
    r"\pm": "±",
    r"\mp": "∓",
    r"\times": "×",
    r"\div": "÷",
    r"\cdot": "·",
    r"\leq": "≤",
    r"\geq": "≥",
    r"\neq": "≠",
    r"\approx": "≈",
    r"\equiv": "≡",
    r"\sim": "∼",
    r"\propto": "∝",
    r"\in": "∈",
    r"\notin": "∉",
    r"\subset": "⊂",
    r"\supset": "⊃",
    r"\cup": "∪",
    r"\cap": "∩",
    r"\emptyset": "∅",
    r"\forall": "∀",
    r"\exists": "∃",
    r"\neg": "¬",
    r"\rightarrow": "→",
    r"\leftarrow": "←",
    r"\Rightarrow": "⇒",
    r"\Leftarrow": "⇐",
    r"\leftrightarrow": "↔",
    r"\ldots": "…",
    r"\cdots": "⋯",
    r"\vdots": "⋮",
    r"\ddots": "⋱",
    r"\hbar": "ħ",
    r"\ell": "ℓ",
    r"\Re": "ℜ",
    r"\Im": "ℑ",
    r"\le": "≤",
    r"\ge": "≥",
    r"\ne": "≠",
    r"\to": "→",
    r"\mapsto": "↦",
    r"\langle": "⟨",
    r"\rangle": "⟩",
    r"\left": "",
    r"\right": "",  # sizing commands, just remove
    r"\quad": " ",
    r"\qquad": "  ",
    r"\,": " ",
    r"\;": " ",
    r"\!": "",
    r"\enspace": " ",
    r"\thinspace": " ",
    r"\dagger": "†",
    r"\ast": "∗",
    r"\star": "⋆",
    r"\circ": "∘",
    r"\bullet": "•",
    r"\oplus": "⊕",
    r"\otimes": "⊗",
    r"\odot": "⊙",
    r"\perp": "⊥",
    r"\parallel": "∥",
}

# Superscript/subscript mappings
SUPERSCRIPTS = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "+": "⁺",
    "-": "⁻",
    "=": "⁼",
    "(": "⁽",
    ")": "⁾",
    "n": "ⁿ",
    "i": "ⁱ",
    "x": "ˣ",
    "y": "ʸ",
    "t": "ᵗ",
    "k": "ᵏ",
    "*": "﹡",
    "dagger": "†",
}

SUBSCRIPTS = {
    "0": "₀",
    "1": "₁",
    "2": "₂",
    "3": "₃",
    "4": "₄",
    "5": "₅",
    "6": "₆",
    "7": "₇",
    "8": "₈",
    "9": "₉",
    "+": "₊",
    "-": "₋",
    "=": "₌",
    "(": "₍",
    ")": "₎",
    "a": "ₐ",
    "e": "ₑ",
    "o": "ₒ",
    "x": "ₓ",
    "y": "ᵧ",
    "z": "ᵤ",
    "i": "ᵢ",
    "j": "ⱼ",
    "k": "ₖ",
    "n": "ₙ",
    "m": "ₘ",
    "t": "ₜ",
}


def sanitize_latex(text: str) -> str:
    """Sanitize raw LaTeX string, handling Dirac notation, hats, matrices, and escape glitches."""
    if not text:
        return ""
    # Normalize double backslashes before pipes and common symbols
    s = text.replace(r"\|", "|").replace(r"\\|", "|")
    # Dirac notation transformations: \ket{x} -> |x⟩, \bra{x} -> ⟨x|, \braket{a}{b} -> ⟨a|b⟩
    s = re.sub(r"\\ket\{([^}]+)\}", r"|\1⟩", s)
    s = re.sub(r"\\bra\{([^}]+)\}", r"⟨\1|", s)
    s = re.sub(r"\\braket\{([^}]+)\}\{([^}]+)\}", r"⟨\1|\2⟩", s)
    s = re.sub(r"\\braket\{([^}]+)\}", r"⟨\1⟩", s)
    # Direct notation with angle brackets
    s = s.replace(r"\vert", "|")
    # Hat and accents
    s = re.sub(r"\\hat\{([A-Za-z0-9])\}", r"\1̂", s)
    s = re.sub(r"\\hat\s*([A-Za-z0-9])", r"\1̂", s)
    s = re.sub(r"\\vec\{([A-Za-z0-9])\}", r"\1⃗", s)
    s = re.sub(r"\\bar\{([A-Za-z0-9])\}", r"\1̄", s)
    s = re.sub(r"\\tilde\{([A-Za-z0-9])\}", r"\1̃", s)
    s = re.sub(r"\\dot\{([A-Za-z0-9])\}", r"\1̇", s)
    s = re.sub(r"\\ddot\{([A-Za-z0-9])\}", r"\1̈", s)
    # Blackboard bold / Mathcal
    s = s.replace(r"\mathbb{R}", "ℝ").replace(r"\mathbb{C}", "ℂ").replace(r"\mathbb{Z}", "ℤ").replace(r"\mathbb{N}", "ℕ")
    s = s.replace(r"\mathbb{Q}", "ℚ").replace(r"\mathbb{H}", "ℍ")
    s = s.replace(r"\mathcal{H}", "ℋ").replace(r"\mathcal{L}", "ℒ").replace(r"\mathcal{O}", "𝒪")
    s = s.replace(r"\mathcal{F}", "ℱ").replace(r"\mathcal{P}", "𝒫")
    # Clean up standard operators
    s = s.replace(r"\infty", "∞")
    s = s.replace(r"\hbar", "ħ")
    s = s.replace(r"\int", "∫")
    s = s.replace(r"\sum", "∑")
    s = s.replace(r"\prod", "∏")
    s = s.replace(r"\partial", "∂")
    s = s.replace(r"\nabla", "∇")
    # Strip dangerous line continuation artifacts
    s = re.sub(r"\\+\n", " ", s)
    return s



def latex_to_unicode(text: str) -> str:
    """Convert LaTeX math notation to Unicode for terminal display."""
    text = sanitize_latex(text)
    # Remove display math delimiters
    text = text.replace(r"\[", "").replace(r"\]", "")
    text = text.replace(r"\(", "").replace(r"\)", "")
    text = text.replace("$$", "").replace("$", "")

    # Convert superscripts: ^{...} or ^x
    def sup_replace(m):
        content = m.group(1) or m.group(2) or ""
        return "".join(SUPERSCRIPTS.get(c, c) for c in content)

    text = re.sub(r"\^\{([^}]*)\}|\^([0-9a-zA-Z\+\-\*\†\∞\ħ\α-\ω])", sup_replace, text)

    # Convert subscripts: _{...} or _x
    def sub_replace(m):
        content = m.group(1) or m.group(2) or ""
        return "".join(SUBSCRIPTS.get(c, c) for c in content)

    text = re.sub(r"_\{([^}]*)\}|_([0-9a-zA-Z\+\-\∞\ħ\α-\ω])", sub_replace, text)

    # Convert fractions: \frac{a}{b} → (a)/(b)
    text = re.sub(r"\\frac\{([^}]*)\}\{([^}]*)\}", r"(\1)/(\2)", text)

    # Convert Greek letters (longer patterns first)
    for latex, uni in sorted(GREEK.items(), key=lambda x: -len(x[0])):
        text = text.replace(latex, uni)

    # Convert operators (longer patterns first)
    for latex, uni in sorted(OPERATORS.items(), key=lambda x: -len(x[0])):
        text = text.replace(latex, uni)

    # Remove remaining backslashes from known styling commands
    text = re.sub(r"\\(?:text|mathrm|mathbf|mathit|mathsf|textbf|textit|bm)\{([^}]*)\}", r"\1", text)
    text = re.sub(
        r"\\(?:sin|cos|tan|sec|csc|cot|log|ln|exp|lim|sup|inf|max|min|det)\b",
        lambda m: m.group(0).lstrip("\\"),
        text,
    )

    # Clean up remaining LaTeX commands
    text = re.sub(r"\\[a-zA-Z]+", "", text)

    # Clean up braces
    text = text.replace("{", "").replace("}", "")

    # Clean up spacing
    text = re.sub(r"  +", " ", text)

    return text.strip()


def render_latex_safe(latex_str: str) -> str:
    """Safely render LaTeX to Unicode, catching all SymPy parser failures."""
    if not latex_str:
        return ""
    sanitized = sanitize_latex(latex_str)
    try:
        from sympy import pretty
        from sympy.parsing.latex import parse_latex

        expr = parse_latex(sanitized)
        return pretty(expr)
    except Exception:
        return latex_to_unicode(sanitized)


def render_equation_box(equation: str, width: int = 60) -> str:
    """Render an equation in a nice terminal box."""
    rendered = latex_to_unicode(equation)
    if len(rendered) > width - 2:
        width = len(rendered) + 4
    lines = []
    lines.append("┌" + "─" * (width - 2) + "┐")
    # Center the equation
    padding = (width - 2 - len(rendered)) // 2
    lines.append(
        "│"
        + " " * max(0, padding)
        + rendered
        + " " * max(0, width - 2 - padding - len(rendered))
        + "│"
    )
    lines.append("└" + "─" * (width - 2) + "┘")
    return "\n".join(lines)


def format_math_in_markdown(content: str) -> str:
    """Convert LaTeX equations inside markdown text into clean Unicode math."""
    if not content:
        return ""

    # Don't touch content inside code blocks
    code_blocks: list[str] = []

    def save_block(m):
        code_blocks.append(m.group(0))
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"

    text = re.sub(r"```[\s\S]*?```", save_block, content)

    # Process block math: $$ ... $$ or \[ ... \]
    def replace_block_math(m):
        math_content = m.group(1).strip()
        rendered = latex_to_unicode(math_content)
        # Multi-line derivations inside structured equation panel / code block
        lines = [f"  {line}" if line else "" for line in rendered.split("\n")]
        formatted = "\n".join(lines)
        return f"\n\n```math\n{formatted}\n```\n\n"

    text = re.sub(r"\$\$([\s\S]+?)\$\$", replace_block_math, text)
    text = re.sub(r"\\\[([\s\S]+?)\\\]", replace_block_math, text)

    # Process inline math: $ ... $ or \( ... \)
    def replace_inline_math(m):
        math_content = m.group(1).strip()
        rendered = latex_to_unicode(math_content)
        return f"`{rendered}`"

    text = re.sub(r"(?<!\\)\$([^$\n]+)\$", replace_inline_math, text)
    text = re.sub(r"\\\(([^)]+)\\\)", replace_inline_math, text)

    # Restore code blocks
    for idx, block in enumerate(code_blocks):
        text = text.replace(f"__CODE_BLOCK_{idx}__", block)

    return text

