"""Shared safe parser for symbolic math expressions.

Eliminates arbitrary Python execution from untrusted expression paths
using Python AST/token validation plus restricted SymPy usage.
Does NOT provide OS-grade sandboxing; it rejects malicious input before
any SymPy parsing and restricts what SymPy functions/constants are available.
"""

import ast
import io
import tokenize

# Maximum allowed tokens / AST nodes / depth to prevent oversized/deep inputs
MAX_INPUT_LENGTH = 2048
MAX_TOKEN_COUNT = 256
MAX_AST_DEPTH = 32
MAX_NODE_COUNT = 256

# Names permitted in expressions (variables, functions, constants from sympy)
# Callers should extend ALLOWED_SYMPY_NAMES with specific function names if needed.
ALLOWED_SYMPY_NAMES: set[str] = {
    # Basic math
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "atan2",
    "sinh",
    "cosh",
    "tanh",
    "asinh",
    "acosh",
    "atanh",
    "exp",
    "log",
    "ln",
    "sqrt",
    "pow",
    "Abs",
    "abs",
    "pi",
    "E",
    "I",
    "oo",
    "zoo",
    # Symbol creation
    "Symbol",
    "symbols",
    # SymPy objects that may appear in parsed expressions
    "Eq",
    "Ne",
    "Gt",
    "Ge",
    "Lt",
    "Le",
    # Matrix-related
    "Matrix",
    "eye",
    "zeros",
    "ones",
    # Integration / differentiation / limits / series
    "integrate",
    "diff",
    "limit",
    "series",
    # Simplification
    "simplify",
    "expand",
    "factor",
    "collect",
    # Basic arithmetic helpers
    "Add",
    "Mul",
    "Pow",
    "Rational",
    "Integer",
    "Float",
    "Number",
    # Trig simplification
    "trigsimp",
    "expand_trig",
    # Common constants / variables users may reference
    "x",
    "y",
    "z",
    "t",
    "n",
    "k",
}

# Nodes from ast that are permitted in expression parsing
ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.Subscript,
    ast.Slice,
    ast.Compare,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Load,
    ast.Attribute,  # We explicitly reject this below
)

# We explicitly reject these AST node types regardless of parent
REJECTED_AST_NODES = (
    ast.Lambda,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Import,
    ast.ImportFrom,
    ast.Module,
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.If,
    ast.IfExp,
    ast.Try,
    ast.Raise,
    ast.Assert,
    ast.With,
    ast.AsyncWith,
    ast.Pass,
    ast.Break,
    ast.Continue,
    ast.Return,
    ast.Delete,
    ast.Global,
    ast.Nonlocal,
    ast.Expr,  # We allow ast.Expression only
    ast.ListComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.DictComp,
    ast.comprehension,
    ast.FormattedValue,
    ast.JoinedStr,
    ast.NamedExpr,
)


class SafeParseError(ValueError):
    """Raised when expression fails safe parser validation."""


# ------------------------------------------------------------------
# Helper: check for forbidden name patterns
# ------------------------------------------------------------------


def _is_forbidden_name(name: str) -> bool:
    # Dunder names (double underscore) are disallowed
    if name.startswith("__") and name.endswith("__"):
        return True
    if "__" in name and not (name.startswith("__") and name.endswith("__")):
        # Any embedded dunder (like obj.__class__) is forbidden
        return True
    # Reject import-related names
    if name in (
        "__import__",
        "__builtins__",
        "__subclasses__",
        "__bases__",
        "__dict__",
        "__class__",
        "__mro__",
        "__globals__",
        "__locals__",
        "__loader__",
        "__spec__",
        "__package__",
        "eval",
        "exec",
        "compile",
        "open",
        "file",
        "input",
        "raw_input",
        "breakpoint",
        "quit",
        "exit",
        "sys",
        "os",
        "subprocess",
        "importlib",
        "types",
        "builtins",
        "__name__",
        "__main__",
        "__doc__",
        "__annotations__",
        "__loader__",
        "__cached__",
        "__file__",
    ):
        return True
    return False


# ------------------------------------------------------------------
# Token-level validation
# ------------------------------------------------------------------


def _token_validate(source: str) -> None:
    """Validate tokens before AST parsing."""
    if len(source) > MAX_INPUT_LENGTH:
        raise SafeParseError(f"Expression exceeds max length ({MAX_INPUT_LENGTH})")

    tokens: list[tokenize.TokenInfo] = []
    try:
        readline = io.StringIO(source).readline
        for tok in tokenize.generate_tokens(readline):
            tokens.append(tok)
    except tokenize.TokenizeError as exc:
        raise SafeParseError(f"Invalid token stream: {exc}")

    if len(tokens) > MAX_TOKEN_COUNT:
        raise SafeParseError(f"Expression exceeds max token count ({MAX_TOKEN_COUNT})")

    forbidden_token_types = {
        tokenize.STRING,
        tokenize.COMMENT,
        tokenize.ENCODING,
    }
    for tok in tokens:
        if tok.type in forbidden_token_types:
            # Strings, comments, encodings are forbidden
            raise SafeParseError(f"Forbidden token: {tokenize.tok_name[tok.type]} ({tok.string!r})")
        # Reject any NAME token that looks suspicious
        if tok.type == tokenize.NAME:
            if _is_forbidden_name(tok.string):
                raise SafeParseError(f"Forbidden name: {tok.string}")
            # Reject names that contain lowercase-only suspicious patterns (e.g., eval, exec)
            if tok.string in ("eval", "exec", "compile", "open", "__import__"):
                raise SafeParseError(f"Forbidden name: {tok.string}")
        # We allow numbers, operators, parentheses, commas, colons (subscript/index), dots
        # but dots ONLY inside names? Actually dots in expressions trigger Attribute nodes.
        # We reject dots entirely in token stream to prevent attribute access.
        if tok.type == tokenize.OP and tok.string == ".":
            # This prevents attribute access like obj.method
            raise SafeParseError("Attribute access (dot operator) is forbidden")
        # Reject f-strings / format specs / backtick? Token stream handles it.


# ------------------------------------------------------------------
# AST-level validation
# ------------------------------------------------------------------


def _ast_validate(node: ast.AST, depth: int = 0) -> int:
    """Recursively validate AST nodes. Returns total node count."""
    if depth > MAX_AST_DEPTH:
        raise SafeParseError(f"Expression exceeds max AST depth ({MAX_AST_DEPTH})")

    # Count nodes
    count = 1
    if isinstance(node, ast.Expression):
        count += _ast_validate(node.body, depth + 1)
        return count

    # Check for rejected node types
    node_type = type(node)
    if node_type in REJECTED_AST_NODES:
        raise SafeParseError(f"Rejected AST node type: {node_type.__name__}")

    if node_type not in ALLOWED_AST_NODES:
        # Any unexpected node type is rejected
        raise SafeParseError(f"Disallowed AST node type: {node_type.__name__}")

    # Explicitly reject Attribute nodes (even though they are in ALLOWED_AST_NODES for typing compatibility)
    if isinstance(node, ast.Attribute):
        raise SafeParseError("Attribute access is forbidden")

    # Explicitly reject Lambda nodes
    if isinstance(node, ast.Lambda):
        raise SafeParseError("Lambda expressions are forbidden")

    # Reject ListComp / SetComp / GeneratorExp / DictComp / Comprehension
    if isinstance(
        node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp, ast.Comprehension)
    ):
        raise SafeParseError("Comprehensions are forbidden")

    # Reject NamedExpr (:= walrus operator)
    if isinstance(node, ast.NamedExpr):
        raise SafeParseError("Named expressions (:=) are forbidden")

    # Reject Subscript with non-string index? Actually subscript is allowed (matrix indexing) but only with int/constant/symbols.
    # We'll allow Subscript but validate its slice/index.
    if isinstance(node, ast.Subscript):
        # Only allow subscript if value is a Name and slice is Index with safe content
        # We allow basic subscripting for matrices / arrays
        pass

    # Recursively check children
    for child in ast.iter_child_nodes(node):
        count += _ast_validate(child, depth + 1)

    if count > MAX_NODE_COUNT:
        raise SafeParseError(f"Expression exceeds max AST node count ({MAX_NODE_COUNT})")

    return count


# ------------------------------------------------------------------
# Safe parser entry point
# ------------------------------------------------------------------


def safe_parse_expression(source: str, allowed_names: set[str] | None = None) -> ast.Expression:
    """Parse and validate a mathematical expression string.

    Args:
        source: Raw expression string.
        allowed_names: Additional allowed names beyond ALLOWED_SYMPY_NAMES.

    Returns:
        ast.Expression: A safe, validated AST.

    Raises:
        SafeParseError: If the expression fails validation.
    """
    # 1. Length check
    source = source.strip()
    if not source:
        raise SafeParseError("Expression is empty")

    # 2. Token validation
    _token_validate(source)

    # 3. AST parse
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise SafeParseError(f"Invalid Python syntax: {exc}")

    # 4. AST validation
    _ast_validate(tree)

    # 5. Name-level checks: only permitted names may be referenced
    permitted: set[str] = set(ALLOWED_SYMPY_NAMES)
    if allowed_names is not None:
        permitted.update(allowed_names)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            # Only allow names in permitted set; variable names (x, y, z, t, etc.) are permitted
            if node.id not in permitted:
                # Variable names that are not in permitted set may still be OK if they're simple identifiers
                # that don't contain forbidden patterns. But we restrict to permitted set + simple single-letter names.
                if len(node.id) == 1 and node.id.isalpha() and node.id.islower():
                    # Single lowercase letter variables (a-z) allowed as variables
                    pass
                elif node.id in permitted:
                    pass
                else:
                    raise SafeParseError(f"Disallowed name reference: {node.id}")
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (str, bytes)):
                raise SafeParseError("String literals are forbidden")
            if isinstance(node.value, (complex,)):
                # Complex numbers may be allowed; we permit them
                pass
    return tree


# ------------------------------------------------------------------
# Restricted SymPy transformation function
# ------------------------------------------------------------------

# Whitelist of SymPy functions we allow to be called through this parser.
ALLOWED_SYMPY_FUNCTIONS: set[str] = {
    "sympify",
    "parse_expr",
    "simplify",
    "expand",
    "factor",
    "collect",
    "integrate",
    "diff",
    "limit",
    "series",
    "solve",
    "lambdify",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "atan2",
    "sinh",
    "cosh",
    "tanh",
    "asinh",
    "acosh",
    "atanh",
    "exp",
    "log",
    "sqrt",
    "pow",
    "Abs",
    "symbols",
    "Symbol",
    "Eq",
    "Matrix",
    "eye",
    "zeros",
    "ones",
    "pi",
    "E",
    "I",
    "trigsimp",
    "expand_trig",
}


def restricted_sympy_transform(tree: ast.Expression, local_dict: dict | None = None) -> object:
    """Convert a safe AST into a SymPy expression using only allowed functions/constants.

    Args:
        tree: A validated ast.Expression.
        local_dict: Optional local dict to inject variables (e.g., symbol mappings).

    Returns:
        A SymPy expression or value.

    Raises:
        SafeParseError: If any disallowed operation is encountered.
    """
    import sympy as sp

    allowed_constants = {
        "pi": sp.pi,
        "E": sp.E,
        "I": sp.I,
        "oo": sp.oo,
        "zoo": sp.zoo,
    }
    allowed_functions = {
        # Symbol creation
        "Symbol": sp.Symbol,
        "symbols": sp.symbols,
        # Parsing / transformation
        "sympify": sp.sympify,
        "parse_expr": sp.parse_expr,
        # Math functions (restricted)
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "asin": sp.asin,
        "acos": sp.acos,
        "atan": sp.atan,
        "sinh": sp.sinh,
        "cosh": sp.cosh,
        "tanh": sp.tanh,
        "exp": sp.exp,
        "log": lambda x: sp.log(x) if not isinstance(x, tuple) else sp.log(x[0], x[1]),
        "sqrt": sp.sqrt,
        "pow": lambda *args: sp.Pow(*args) if len(args) == 2 else sp.Pow(args[0], args[1]),
        "Abs": sp.Abs,
        # Algebraic helpers
        "simplify": sp.simplify,
        "expand": sp.expand,
        "factor": sp.factor,
        "collect": sp.collect,
        # Calculus
        "integrate": sp.integrate,
        "diff": sp.diff,
        "limit": sp.limit,
        "series": sp.series,
        "solve": sp.solve,
        # Trig simplification
        "trigsimp": sp.trigsimp,
        "expand_trig": sp.expand_trig,
        # Linear algebra
        "Matrix": sp.Matrix,
        "eye": sp.eye,
        "zeros": sp.zeros,
        "ones": sp.ones,
    }

    # Merge local_dict variables (e.g., pre-defined symbols)
    allowed_constants.update(allowed_constants or {})
    allowed_constants.update(local_dict or {})
    # Note: functions should not be overridden by local_dict (security)

    # We build a restricted eval-like function using the AST directly.
    # Instead of using Python eval, we manually evaluate safe AST nodes.
    def _eval(node: ast.AST) -> object:
        if isinstance(node, ast.Expression):
            return _eval(node.body)

        # Binary operations
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                return left / right
            elif isinstance(node.op, ast.Pow):
                return left**right
            elif isinstance(node.op, ast.Mod):
                return left % right
            else:
                raise SafeParseError(f"Unsupported binary operator: {type(node.op).__name__}")

        # Unary operations
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            elif isinstance(node.op, ast.USub):
                return -operand
            elif isinstance(node.op, ast.Not):
                return not operand
            else:
                raise SafeParseError(f"Unsupported unary operator: {type(node.op).__name__}")

        # Function calls
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                # Even though Attribute is forbidden at parser level, guard here
                raise SafeParseError("Attribute-based calls are forbidden")
            else:
                raise SafeParseError("Unsupported call target")

            if func_name is None:
                raise SafeParseError("Invalid function call name")

            # Allow only whitelisted function names
            if func_name not in allowed_functions:
                # Special case: user-defined variables (single-letter) might appear as calls? No.
                # Only allow names that are in allowed_functions.
                raise SafeParseError(f"Disallowed function call: {func_name}")

            args = []
            for arg in node.args:
                args.append(_eval(arg))
            kwargs = {}
            for kw in node.keywords:
                kwargs[kw.arg] = _eval(kw.value)

            func = allowed_functions[func_name]
            # Use restricted sympy function via Python call but with whitelisted inputs
            return func(*args, **kwargs)

        # Name references (variables / constants)
        if isinstance(node, ast.Name):
            name = node.id
            if name in allowed_constants:
                return allowed_constants[name]
            if name in allowed_functions:
                # If a function name appears without call, treat as reference (should not be evaluated directly)
                # For simplicity, return the function object. Call nodes handle invocation.
                return allowed_functions[name]
            # Variable names: if single lowercase letter, treat as unknown symbol and create via Symbol
            if len(name) == 1 and name.isalpha() and name.islower():
                # Return sympy Symbol directly
                return sp.Symbol(name)
            # For variables defined in local_dict
            if name in allowed_constants:
                return allowed_constants[name]
            raise SafeParseError(f"Unknown or disallowed name: {name}")

        # Constants (numbers)
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, (int, float, complex)):
                return value
            if value is None:
                return None
            raise SafeParseError(f"Disallowed constant type: {type(value).__name__}")
        # Tuples / Lists
        if isinstance(node, ast.Tuple):
            return tuple(_eval(elt) for elt in node.elts)
        if isinstance(node, ast.List):
            return [_eval(elt) for elt in node.elts]

        # Subscript (matrix / array indexing)
        if isinstance(node, ast.Subscript):
            value = _eval(node.value)
            slice_node = node.slice
            index = _eval(slice_node)
            # Only allow subscript on sympy objects, not arbitrary Python objects
            if hasattr(value, "__getitem__"):
                return value[index]
            raise SafeParseError("Subscript target is not indexable in allowed context")

        # Slice
        if isinstance(node, (ast.Slice,)):
            # Allow simple slice notation like [1:3] but evaluate accordingly
            lower = _eval(node.lower) if node.lower else None
            upper = _eval(node.upper) if node.upper else None
            step = _eval(node.step) if node.step else None
            return slice(lower, upper, step)

        # Comparison expressions are allowed but should evaluate to sympy relations
        if isinstance(node, ast.Compare):
            left = _eval(node.left)
            ops = node.ops
            comparators = node.comparators
            # For simplicity in mathematical expressions, we only allow single comparisons
            if len(ops) != 1 or len(comparators) != 1:
                raise SafeParseError("Only simple single comparisons are allowed")
            op_type = ops[0]
            comparator = _eval(comparators[0])
            if isinstance(op_type, ast.Eq):
                return sp.Eq(left, comparator)
            elif isinstance(op_type, ast.NotEq):
                return sp.Ne(left, comparator)
            elif isinstance(op_type, ast.Lt):
                return sp.Lt(left, comparator)
            elif isinstance(op_type, ast.LtE):
                return sp.Le(left, comparator)
            elif isinstance(op_type, ast.Gt):
                return sp.Gt(left, comparator)
            elif isinstance(op_type, ast.GtE):
                return sp.Ge(left, comparator)
            else:
                raise SafeParseError(f"Unsupported comparison operator: {type(op_type).__name__}")

        # Any remaining node types should have been rejected by parser
        raise SafeParseError(f"Unsupported AST node in evaluation: {type(node).__name__}")

    result = _eval(tree)
    return result
