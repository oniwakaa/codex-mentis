from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional, Tuple
from pitagora.math_engine.sandbox import SymPySandbox, SandboxResult

@dataclass
class ProofResult:
    verified: bool
    steps: List[str] = field(default_factory=list)
    latex_lhs: str = ""
    latex_rhs: str = ""
    error: Optional[str] = None

@dataclass
class Solution:
    solutions: List[str] = field(default_factory=list)
    latex: str = ""
    steps: List[str] = field(default_factory=list)
    error: Optional[str] = None

@dataclass
class SeriesResult:
    expr: str = ""
    latex: str = ""
    steps: List[str] = field(default_factory=list)
    error: Optional[str] = None

@dataclass
class FactoredForm:
    expr: str = ""
    latex: str = ""
    error: Optional[str] = None

@dataclass
class SimplifiedForm:
    expr: str = ""
    latex: str = ""
    error: Optional[str] = None

@dataclass
class SubstitutionResult:
    expr: str = ""
    latex: str = ""
    error: Optional[str] = None

class SymbolicMath:
    def __init__(self, sandbox: Optional[SymPySandbox] = None):
        self.sandbox = sandbox or SymPySandbox()

    def prove_identity(self, lhs: str, rhs: str, variables: List[str]) -> ProofResult:
        """Proves that LHS equals RHS by simplifying LHS - RHS to zero."""
        code = """
        lhs_str = data['lhs']
        rhs_str = data['rhs']
        vars_list = data['variables']
        
        # Define symbols
        for v in vars_list:
            context[v] = sp.Symbol(v)
            
        lhs_expr = sp.sympify(lhs_str, locals=context)
        rhs_expr = sp.sympify(rhs_str, locals=context)
        
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
            # Try further expansion/simplification
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
        """
        res = self.sandbox._execute_in_isolated_process(code, {
            "lhs": lhs,
            "rhs": rhs,
            "variables": variables
        })
        if "error" in res:
            return ProofResult(verified=False, error=res["error"])
        return ProofResult(
            verified=res.get("verified", False),
            steps=res.get("steps", []),
            latex_lhs=res.get("latex_lhs", ""),
            latex_rhs=res.get("latex_rhs", "")
        )

    def solve_ode(self, ode_str: str, func: str) -> Solution:
        """Solves an ordinary differential equation (ODE) for function func, e.g. f(x)."""
        code = """
        ode_s = data['ode']
        func_s = data['func']
        
        # Parse function and variable, e.g. f(x) -> function f, variable x
        if '(' in func_s and func_s.endswith(')'):
            f_name, var_name = func_s[:-1].split('(', 1)
            x = sp.Symbol(var_name)
            context[var_name] = x
            f = sp.Function(f_name)(x)
            context[f_name] = sp.Function(f_name)
        else:
            raise ValueError("Function must be specified in the format f(x)")
            
        # Parse ODE
        if '=' in ode_s:
            lhs_s, rhs_s = ode_s.split('=', 1)
            lhs = sp.sympify(lhs_s, locals=context)
            rhs = sp.sympify(rhs_s, locals=context)
            eq = lhs - rhs
        else:
            eq = sp.sympify(ode_s, locals=context)
            
        sol = sp.dsolve(eq, f)
        
        steps = [
            f"Solving ODE: {eq} = 0",
            f"Solving for function: {f}"
        ]
        
        # sol can be an Eq or list of Eqs
        if isinstance(sol, list):
            sols = [str(s) for s in sol]
            latex_val = sp.latex(sol)
        else:
            sols = [str(sol)]
            latex_val = sp.latex(sol)
            
        print(json.dumps({
            "solutions": sols,
            "latex": latex_val,
            "steps": steps
        }))
        """
        res = self.sandbox._execute_in_isolated_process(code, {
            "ode": ode_str,
            "func": func
        })
        if "error" in res:
            return Solution(error=res["error"])
        return Solution(
            solutions=res.get("solutions", []),
            latex=res.get("latex", ""),
            steps=res.get("steps", [])
        )

    def taylor_expand(self, expr: str, var: str, point: str, order: int) -> SeriesResult:
        """Generates Taylor series expansion of expr around var=point up to order."""
        sandbox_res = self.sandbox.series(expr, var, point, order)
        if sandbox_res.error:
            return SeriesResult(error=sandbox_res.error)
        return SeriesResult(
            expr=sandbox_res.value,
            latex=sandbox_res.latex,
            steps=sandbox_res.steps
        )

    def factor(self, expr: str) -> FactoredForm:
        """Factors a symbolic expression."""
        code = """
        expr_str = data['expr']
        expression = sp.sympify(expr_str, locals=context)
        res = sp.factor(expression)
        print(json.dumps({
            "expr": str(res),
            "latex": sp.latex(res)
        }))
        """
        res = self.sandbox._execute_in_isolated_process(code, {"expr": expr})
        if "error" in res:
            return FactoredForm(error=res["error"])
        return FactoredForm(expr=res.get("expr", ""), latex=res.get("latex", ""))

    def simplify(self, expr: str) -> SimplifiedForm:
        """Simplifies a symbolic expression."""
        code = """
        expr_str = data['expr']
        expression = sp.sympify(expr_str, locals=context)
        res = sp.simplify(expression)
        print(json.dumps({
            "expr": str(res),
            "latex": sp.latex(res)
        }))
        """
        res = self.sandbox._execute_in_isolated_process(code, {"expr": expr})
        if "error" in res:
            return SimplifiedForm(error=res["error"])
        return SimplifiedForm(expr=res.get("expr", ""), latex=res.get("latex", ""))

    def substitute(self, expr: str, substitutions: Dict[str, str]) -> SubstitutionResult:
        """Substitutes variables/expressions in expr using substitutions mapping."""
        code = """
        expr_str = data['expr']
        subs_dict = data['substitutions']
        
        expression = sp.sympify(expr_str, locals=context)
        
        # Build substitution list
        subs = []
        for k, v in subs_dict.items():
            subs.append((sp.sympify(k, locals=context), sp.sympify(v, locals=context)))
            
        res = expression.subs(subs)
        print(json.dumps({
            "expr": str(res),
            "latex": sp.latex(res)
        }))
        """
        res = self.sandbox._execute_in_isolated_process(code, {
            "expr": expr,
            "substitutions": substitutions
        })
        if "error" in res:
            return SubstitutionResult(error=res["error"])
        return SubstitutionResult(expr=res.get("expr", ""), latex=res.get("latex", ""))
