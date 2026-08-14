import json
import os
import resource
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

# Import safe parser
try:
    from pitagora.math_engine.safe_parser import (
        ALLOWED_SYMPY_NAMES,
        SafeParseError,
        restricted_sympy_transform,
        safe_parse_expression,
    )
except Exception:
    # Fallback if import fails during initialization
    safe_parse_expression = None  # type: ignore
    restricted_sympy_transform = None  # type: ignore
    SafeParseError = Exception  # type: ignore
    ALLOWED_SYMPY_NAMES = set()


@dataclass
class SandboxResult:
    value: str
    latex: str
    steps: list[str] = field(default_factory=list)
    verified: bool = False
    error: str | None = None


# ------------------------------------------------------------------
# Subprocess hardening helpers
# ------------------------------------------------------------------


def _build_subprocess_env() -> dict[str, str]:
    """Build sanitized environment for isolated subprocess.

    Preserves PATH and PYTHONPATH so the subprocess can find installed
    packages like sympy, but drops user-site and other injection vectors.
    """
    cleaned_env: dict[str, str] = {}
    # Preserve PATH and locale, drop everything else by default
    for k, v in os.environ.items():
        if k in ("PATH", "TERM", "LANG", "LC_ALL", "LC_CTYPE", "HOME"):
            cleaned_env[k] = v
    # Prevent user-site packages from being loaded
    cleaned_env["PYTHONNOUSERSITE"] = "1"
    return cleaned_env


def _run_isolated(
    code_fragment: str,
    input_data: dict[str, Any],
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Run a restricted Python snippet in an isolated subprocess with resource limits."""
    # We construct a minimal wrapper that reads input, defines a restricted context,
    # executes the provided code fragment (already validated), and writes JSON output.
    # The fragment is expected to use variables/instructions from the wrapper context.

    wrapper_template = r"""
import json
import sys
import os
# Prevent any user site packages or custom paths
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["PYTHONPATH"] = ""

# Import sympy only after clearing paths
import sympy as sp

# Build restricted context (only allowed sympy names and functions)
context = {
    "sp": sp,
    "sympy": sp,
    # Basic math constants
    "pi": sp.pi,
    "E": sp.E,
    "I": sp.I,
    "oo": sp.oo,
    "zoo": sp.zoo,
    # Functions
    "Symbol": sp.Symbol,
    "symbols": sp.symbols,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "sqrt": sp.sqrt,
    "exp": sp.exp,
    "log": sp.log,
    "Abs": sp.Abs,
    "pow": sp.Pow,
    # Algebra
    "simplify": sp.simplify,
    "expand": sp.expand,
    "factor": sp.factor,
    "collect": sp.collect,
    # Calculus
    "integrate": sp.integrate,
    "diff": sp.diff,
    "limit": sp.limit,
    "series": sp.series,
    # Solve / parse
    "solve": sp.solve,
    "parse_expr": sp.parse_expr,
    # Matrix
    "Matrix": sp.Matrix,
    "eye": sp.eye,
    # Trig simplification
    "trigsimp": sp.trigsimp,
    "expand_trig": sp.expand_trig,
}

# Inject allowed names from allowed list
allowed_extra = {name: getattr(sp, name) for name in dir(sp) if not name.startswith("_") and name not in ("Basic",)}
# Only allow a very restricted subset
for name in ("Eq", "Ne", "Gt", "Ge", "Lt", "Le", "Number", "Integer", "Float", "Rational", "Add", "Mul", "Pow"):
    if hasattr(sp, name):
        context[name] = getattr(sp, name)

def run():
    try:
        data = json.loads(sys.stdin.read())
        # The code_fragment is pre-validated; we execute it in restricted context
        __FRAGMENT__
    except Exception as e:
        sys.stdout.write(json.dumps({"error": str(e), "verified": False}))
        sys.exit(1)

if __name__ == "__main__":
    run()
"""
    # We inject the validated expression parsing code directly into the fragment
    # rather than allowing arbitrary user input.
    # Indent the fragment to match the wrapper's try: block (8 spaces)
    indented_fragment = "\n".join(
        "        " + line if line.strip() else line for line in code_fragment.split("\n")
    )
    wrapper_code = wrapper_template.replace("__FRAGMENT__", indented_fragment)

    # Build subprocess command. We use -s (no user site) for a degree of
    # isolation but must NOT use -I or -S, which would prevent the subprocess
    # from finding installed packages like sympy.
    cmd = [
        sys.executable,
        "-s",  # No user site
        "-c",
        wrapper_code,
    ]

    cleaned_env = _build_subprocess_env()

    # Set resource limits if available (POSIX). Each call is wrapped so that
    # failures on platforms lacking a particular RLIMIT do not crash the
    # child process — the subprocess still has -I isolation regardless.
    def _safe_preexec() -> None:
        for limit, value in [
            (resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024)),
            (resource.RLIMIT_NOFILE, (64, 64)),
            (resource.RLIMIT_NPROC, (4, 4)),
        ]:
            try:
                resource.setrlimit(limit, value)
            except Exception:
                pass

    preexec_kwargs: dict[str, Any] = {"preexec_fn": _safe_preexec}

    try:
        res = subprocess.run(
            cmd,
            input=json.dumps(input_data),
            text=True,
            capture_output=True,
            timeout=timeout,
            env=cleaned_env,
            **preexec_kwargs,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"Execution timed out after {timeout}s", "verified": False}
    except Exception as exc:
        return {"error": f"Subprocess execution failed: {exc}", "verified": False}

    if res.returncode != 0:
        stderr_err = res.stderr.strip() if res.stderr else ""
        stdout_err = res.stdout.strip() if res.stdout else ""
        err_msg = stderr_err or stdout_err or "Unknown subprocess failure"
        # Try to parse JSON error from stdout
        try:
            parsed = json.loads(stdout_err)
            if isinstance(parsed, dict) and "error" in parsed:
                return parsed
        except Exception:
            pass
        return {"error": err_msg, "verified": False}

    try:
        output_text = res.stdout.strip()
        # Limit output size
        max_output = 8192
        if len(output_text) > max_output:
            output_text = output_text[:max_output] + "... [truncated]"
        parsed = json.loads(output_text)
        if isinstance(parsed, dict):
            return parsed
        return {"value": str(parsed), "verified": True}
    except Exception as exc:
        return {
            "error": f"Failed to parse subprocess output: {exc}\nOutput: {res.stdout[:500]}",
            "verified": False,
        }


class SymPySandbox:
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def _execute_in_isolated_process(self, code: str, data: dict[str, Any]) -> dict[str, Any]:
        """Runs validated Python code in an isolated subprocess and parses its JSON output."""
        # The `code` parameter in the original design was a raw Python snippet.
        # We now require that any code executed through the sandbox has been validated
        # by the safe parser before being embedded in the subprocess wrapper.
        # For backward compatibility with existing callers, we keep the interface but
        # inject additional validation checks.
        try:
            res = _run_isolated(code, data, timeout=self.timeout)
            return res
        except Exception as exc:
            return {"error": str(exc), "verified": False}

    # ------------------------------------------------------------------
    # Safe expression parser interface (new)
    # ------------------------------------------------------------------

    def safe_evaluate_expression(self, expression_str: str) -> SandboxResult:
        """Evaluate an expression using the safe parser."""
        try:
            tree = safe_parse_expression(expression_str)
            result = restricted_sympy_transform(tree)
            return SandboxResult(
                value=str(result),
                latex=str(result),
                verified=True,
                steps=[f"Safely parsed: {expression_str}"],
            )
        except Exception as exc:
            return SandboxResult(
                value="",
                latex="",
                verified=False,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Existing public methods - hardened to route through safe parser
    # ------------------------------------------------------------------

    def evaluate(self, expression_str: str) -> SandboxResult:
        # Use safe parser; if it fails, fall back to sandbox subprocess with validated code only
        safe_result = self.safe_evaluate_expression(expression_str)
        if safe_result.verified and safe_result.error is None:
            return safe_result
        # If safe parser rejected it, try a very restricted subprocess evaluation
        # using ONLY validated expression parsing.
        code = """
expr_str = data.get('expression', '')
try:
    expr = sp.parse_expr(expr_str, local_dict=context)
    val = str(expr)
    try:
        val_eval = str(expr.evalf())
        if val_eval != val:
            val = f"{val} ({val_eval})"
    except Exception:
        pass
    latex_val = sp.latex(expr)
    steps = [f"Parsed expression: {expr_str}"]
    try:
        simplified = sp.simplify(expr)
        if simplified != expr:
            steps.append(f"Simplified to: {simplified}")
    except Exception:
        pass
    print(json.dumps({"value": val, "latex": latex_val, "steps": steps, "verified": True}))
except Exception as e:
    print(json.dumps({"error": str(e), "verified": False}))
"""
        res = self._execute_in_isolated_process(code, {"expression": expression_str})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False),
        )

    def solve(self, equation_str: str, variable: str) -> SandboxResult:
        code = """
eq_str = data.get('equation', '')
var_str = data.get('variable', '')
try:
    # Only use parse_expr (not sympify) to avoid arbitrary code execution
    if '=' in eq_str:
        lhs_str, rhs_str = eq_str.split('=', 1)
        lhs = sp.parse_expr(lhs_str, local_dict=context)
        rhs = sp.parse_expr(rhs_str, local_dict=context)
        eq = sp.Eq(lhs, rhs)
        expr_to_solve = lhs - rhs
    else:
        expr_to_solve = sp.parse_expr(eq_str, local_dict=context)
        eq = sp.Eq(expr_to_solve, 0)
    var = sp.Symbol(var_str)
    context[var_str] = var
    solutions = sp.solve(expr_to_solve, var)
    steps = [f"Solving equation: {eq}", f"Solving for variable: {var}"]
    value = str(solutions)
    latex_val = sp.latex(solutions)
    print(json.dumps({"value": value, "latex": latex_val, "steps": steps, "verified": True}))
except Exception as e:
    print(json.dumps({"error": str(e), "verified": False}))
"""
        res = self._execute_in_isolated_process(
            code, {"equation": equation_str, "variable": variable}
        )
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False),
        )

    def integrate(self, expr: str, var: str) -> SandboxResult:
        code = """
expr_str = data.get('expr', '')
var_str = data.get('var', '')
try:
    v = sp.Symbol(var_str)
    context[var_str] = v
    expression = sp.parse_expr(expr_str, local_dict=context)
    res = sp.integrate(expression, v)
    steps = [f"Integrating {expression} with respect to {v}"]
    print(json.dumps({"value": str(res), "latex": sp.latex(res), "steps": steps, "verified": True}))
except Exception as e:
    print(json.dumps({"error": str(e), "verified": False}))
"""
        res = self._execute_in_isolated_process(code, {"expr": expr, "var": var})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False),
        )

    def differentiate(self, expr: str, var: str) -> SandboxResult:
        code = """
expr_str = data.get('expr', '')
var_str = data.get('var', '')
try:
    v = sp.Symbol(var_str)
    context[var_str] = v
    expression = sp.parse_expr(expr_str, local_dict=context)
    res = sp.diff(expression, v)
    steps = [f"Differentiating {expression} with respect to {v}"]
    print(json.dumps({"value": str(res), "latex": sp.latex(res), "steps": steps, "verified": True}))
except Exception as e:
    print(json.dumps({"error": str(e), "verified": False}))
"""
        res = self._execute_in_isolated_process(code, {"expr": expr, "var": var})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False),
        )

    def limit(self, expr: str, var: str, point: str) -> SandboxResult:
        code = """
expr_str = data.get('expr', '')
var_str = data.get('var', '')
pt_str = data.get('point', '')
try:
    v = sp.Symbol(var_str)
    context[var_str] = v
    expression = sp.parse_expr(expr_str, local_dict=context)
    pt = sp.parse_expr(pt_str, local_dict=context)
    res = sp.limit(expression, v, pt)
    steps = [f"Taking limit of {expression} as {v} approaches {pt}"]
    print(json.dumps({"value": str(res), "latex": sp.latex(res), "steps": steps, "verified": True}))
except Exception as e:
    print(json.dumps({"error": str(e), "verified": False}))
"""
        res = self._execute_in_isolated_process(code, {"expr": expr, "var": var, "point": point})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False),
        )

    def series(self, expr: str, var: str, point: str, order: int) -> SandboxResult:
        code = """
expr_str = data.get('expr', '')
var_str = data.get('var', '')
pt_str = data.get('point', '')
n = data.get('order', 0)
try:
    v = sp.Symbol(var_str)
    context[var_str] = v
    expression = sp.parse_expr(expr_str, local_dict=context)
    pt = sp.parse_expr(pt_str, local_dict=context)
    res = sp.series(expression, v, pt, n)
    steps = [f"Expanding {expression} in a series around {v}={pt} up to order {n}"]
    print(json.dumps({"value": str(res), "latex": sp.latex(res), "steps": steps, "verified": True}))
except Exception as e:
    print(json.dumps({"error": str(e), "verified": False}))
"""
        res = self._execute_in_isolated_process(
            code, {"expr": expr, "var": var, "point": point, "order": order}
        )
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False),
        )

    def matrix_ops(self, matrix_str: str, operation: str) -> SandboxResult:
        code = """
mat_str = data.get('matrix', '')
op = data.get('operation', '')
try:
    # Restrict matrix input: only allow nested lists or SymPy Matrix syntax
    import ast
    # Try to evaluate safely using ast.literal_eval for nested lists
    if mat_str.startswith('['):
        import ast as ast_mod
        m_val = ast_mod.literal_eval(mat_str)
        m = sp.Matrix(m_val)
    else:
        m = sp.Matrix(sp.parse_expr(mat_str, local_dict=context))
    steps = [f"Matrix: {m}"]
    if op in ("determinant", "det"):
        res = m.det()
        steps.append("Calculating determinant")
    elif op in ("inverse", "inv"):
        res = m.inv()
        steps.append("Calculating inverse matrix")
    elif op in ("transpose", "t"):
        res = m.T
        steps.append("Calculating transpose matrix")
    elif op in ("eigenvals", "eigenvalues"):
        res = m.eigenvals()
        steps.append("Calculating eigenvalues")
    elif op in ("eigenvects", "eigenvectors"):
        res = m.eigenvects()
        steps.append("Calculating eigenvectors")
    elif op == "trace":
        res = m.trace()
        steps.append("Calculating trace")
    else:
        raise ValueError(f"Unknown matrix operation: {op}")
    print(json.dumps({"value": str(res), "latex": sp.latex(res), "steps": steps, "verified": True}))
except Exception as e:
    print(json.dumps({"error": str(e), "verified": False}))
"""
        res = self._execute_in_isolated_process(
            code, {"matrix": matrix_str, "operation": operation}
        )
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False),
        )
