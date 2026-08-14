from dataclasses import dataclass, field

from pitagora.math_engine.safe_parser import (
    safe_parse_expression,
)
from pitagora.math_engine.sandbox import SymPySandbox


@dataclass
class ProofResult:
    verified: bool
    steps: list[str] = field(default_factory=list)
    latex_lhs: str = ""
    latex_rhs: str = ""
    error: str | None = None


@dataclass
class Solution:
    solutions: list[str] = field(default_factory=list)
    latex: str = ""
    steps: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class SeriesResult:
    expr: str = ""
    latex: str = ""
    steps: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class FactoredForm:
    expr: str = ""
    latex: str = ""
    error: str | None = None


@dataclass
class SimplifiedForm:
    expr: str = ""
    latex: str = ""
    error: str | None = None


@dataclass
class SubstitutionResult:
    expr: str = ""
    latex: str = ""
    error: str | None = None


class SymbolicMath:
    def __init__(self, sandbox: SymPySandbox | None = None):
        self.sandbox = sandbox or SymPySandbox()

    def prove_identity(self, lhs: str, rhs: str, variables: list[str]) -> ProofResult:
        """Proves that LHS equals RHS by simplifying LHS - RHS to zero using safe parser."""
        # Route through safe parser before any SymPy transformation
        try:
            # Validate LHS and RHS expressions individually
            safe_parse_expression(lhs)
            safe_parse_expression(rhs)
            # Build variables mapping
            local_dict = {}
            for v in variables:
                local_dict[v] = f"Symbol('{v}')"
            # Use sandbox with restricted code that avoids sympify
            code = """
try:
    lhs_expr = sp.parse_expr(lhs_str, local_dict=context)
    rhs_expr = sp.parse_expr(rhs_str, local_dict=context)
    diff = lhs_expr - rhs_expr
    simplified = sp.simplify(diff)
    verified = (simplified == 0)
    steps = [
        f"Comparing LHS: {lhs_expr} and RHS: {rhs_expr}",
        f"Difference (LHS - RHS): {diff}",
        f"Simplified difference: {simplified}"
    ]
    if verified:
        steps.append("LHS matches RHS identically (difference is 0)")
    else:
        trig_simp = sp.trigsimp(diff)
        if trig_simp == 0:
            verified = True
            steps.append("Identity proven using trigonometric simplification")
        else:
            steps.append("LHS does not match RHS identically")
    print(json.dumps({
        "verified": verified,
        "steps": steps,
        "latex_lhs": sp.latex(lhs_expr),
        "latex_rhs": sp.latex(rhs_expr)
    }))
except Exception as e:
    print(json.dumps({"error": str(e), "verified": False}))
"""
            # Define symbols in data context
            {v: v for v in variables}
            res = self.sandbox._execute_in_isolated_process(
                code,
                {
                    "lhs": lhs,
                    "rhs": rhs,
                    "variables": variables,
                },
            )
            if "error" in res:
                return ProofResult(verified=False, error=res["error"])
            return ProofResult(
                verified=res.get("verified", False),
                steps=res.get("steps", []),
                latex_lhs=res.get("latex_lhs", ""),
                latex_rhs=res.get("latex_rhs", ""),
            )
        except Exception as exc:
            return ProofResult(verified=False, error=str(exc))

    def solve_ode(self, ode_str: str, func: str) -> Solution:
        """Solves an ordinary differential equation (ODE) for function func, e.g. f(x)."""
        try:
            safe_parse_expression(ode_str)
            # Build restricted code that uses parse_expr not sympify
            code = """
try:
    ode_s = data.get('ode', '')
    func_s = data.get('func', '')
    if '(' in func_s and func_s.endswith(')'):
        f_name, var_name = func_s[:-1].split('(', 1)
        x = sp.Symbol(var_name)
        context[var_name] = x
        f = sp.Function(f_name)(x)
        context[f_name] = sp.Function(f_name)
    else:
        raise ValueError("Function must be specified in the format f(x)")
    if '=' in ode_s:
        lhs_s, rhs_s = ode_s.split('=', 1)
        lhs = sp.parse_expr(lhs_s, local_dict=context)
        rhs = sp.parse_expr(rhs_s, local_dict=context)
        eq = lhs - rhs
    else:
        eq = sp.parse_expr(ode_s, local_dict=context)
    sol = sp.dsolve(eq, f)
    steps = [f"Solving ODE: {eq} = 0", f"Solving for function: {f}"]
    if isinstance(sol, list):
        sols = [str(s) for s in sol]
        latex_val = sp.latex(sol)
    else:
        sols = [str(sol)]
        latex_val = sp.latex(sol)
    print(json.dumps({"solutions": sols, "latex": latex_val, "steps": steps}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
"""
            res = self.sandbox._execute_in_isolated_process(code, {"ode": ode_str, "func": func})
            if "error" in res:
                return Solution(error=res["error"])
            return Solution(
                solutions=res.get("solutions", []),
                latex=res.get("latex", ""),
                steps=res.get("steps", []),
            )
        except Exception as exc:
            return Solution(error=str(exc))

    def taylor_expand(self, expr: str, var: str, point: str, order: int) -> SeriesResult:
        """Generates Taylor series expansion of expr around var=point up to order."""
        sandbox_res = self.sandbox.series(expr, var, point, order)
        if sandbox_res.error:
            return SeriesResult(error=sandbox_res.error)
        return SeriesResult(
            expr=sandbox_res.value, latex=sandbox_res.latex, steps=sandbox_res.steps
        )

    def factor(self, expr: str) -> FactoredForm:
        """Factors a symbolic expression using safe parser."""
        try:
            safe_parse_expression(expr)
            code = """
try:
    expression = sp.parse_expr(expr_str, local_dict=context)
    res = sp.factor(expression)
    print(json.dumps({"expr": str(res), "latex": sp.latex(res)}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
"""
            res = self.sandbox._execute_in_isolated_process(code, {"expr": expr})
            if "error" in res:
                return FactoredForm(error=res["error"])
            return FactoredForm(expr=res.get("expr", ""), latex=res.get("latex", ""))
        except Exception as exc:
            return FactoredForm(error=str(exc))

    def simplify(self, expr: str) -> SimplifiedForm:
        """Simplifies a symbolic expression using safe parser."""
        try:
            safe_parse_expression(expr)
            code = """
try:
    expression = sp.parse_expr(expr_str, local_dict=context)
    res = sp.simplify(expression)
    print(json.dumps({"expr": str(res), "latex": sp.latex(res)}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
"""
            res = self.sandbox._execute_in_isolated_process(code, {"expr": expr})
            if "error" in res:
                return SimplifiedForm(error=res["error"])
            return SimplifiedForm(expr=res.get("expr", ""), latex=res.get("latex", ""))
        except Exception as exc:
            return SimplifiedForm(error=str(exc))

    def substitute(self, expr: str, substitutions: dict[str, str]) -> SubstitutionResult:
        """Substitutes variables/expressions in expr using safe parser."""
        try:
            safe_parse_expression(expr)
            # Validate substitution values too
            for k, v in substitutions.items():
                safe_parse_expression(str(k))
                safe_parse_expression(str(v))
            code = """
try:
    expression = sp.parse_expr(expr_str, local_dict=context)
    subs_dict = data.get('substitutions', {})
    subs = []
    for k, v in subs_dict.items():
        subs.append((sp.parse_expr(str(k), local_dict=context), sp.parse_expr(str(v), local_dict=context)))
    res = expression.subs(subs)
    print(json.dumps({"expr": str(res), "latex": sp.latex(res)}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
"""
            res = self.sandbox._execute_in_isolated_process(
                code,
                {
                    "expr": expr,
                    "substitutions": substitutions,
                },
            )
            if "error" in res:
                return SubstitutionResult(error=res["error"])
            return SubstitutionResult(expr=res.get("expr", ""), latex=res.get("latex", ""))
        except Exception as exc:
            return SubstitutionResult(error=str(exc))
