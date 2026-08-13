import sys
import json
import subprocess
from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional, Tuple

@dataclass
class SandboxResult:
    value: str
    latex: str
    steps: List[str] = field(default_factory=list)
    verified: bool = False
    error: Optional[str] = None

class SymPySandbox:
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def _execute_in_isolated_process(self, code: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Runs Python code in an isolated subprocess and parses its JSON output."""
        input_data = json.dumps(data)
        
        # Python code to be run in the subprocess
        wrapper_code = f"""
import json
import sys
import sympy as sp
import numpy as np
import scipy as sc

def run():
    try:
        data = json.loads(sys.stdin.read())
        # Let symbols be defined dynamically if needed
        # We also define common math functions in the local context
        context = {{
            'sp': sp, 'np': np, 'sc': sc, 'sympy': sp, 'numpy': np, 'scipy': sc,
            'symbols': sp.symbols, 'Symbol': sp.Symbol
        }}
        # Inject sympy functions/constants directly into context for easier evaluation
        for name in dir(sp):
            if not name.startswith('_'):
                context[name] = getattr(sp, name)
                
        {code}
    except Exception as e:
        print(json.dumps({{"error": str(e), "verified": False}}))
        sys.exit(1)

if __name__ == '__main__':
    run()
"""
        try:
            res = subprocess.run(
                [sys.executable, "-c", wrapper_code],
                input=input_data,
                text=True,
                capture_output=True,
                timeout=self.timeout
            )
            if res.returncode != 0:
                stderr_err = res.stderr.strip()
                stdout_err = res.stdout.strip()
                err_msg = stderr_err or stdout_err or "Unknown subprocess failure"
                try:
                    parsed = json.loads(stdout_err)
                    if "error" in parsed:
                        return parsed
                except Exception:
                    pass
                return {"error": err_msg, "verified": False}
            
            return json.loads(res.stdout.strip())
        except subprocess.TimeoutExpired:
            return {"error": f"Execution timed out after {self.timeout}s", "verified": False}
        except Exception as e:
            return {"error": str(e), "verified": False}

    def evaluate(self, expression_str: str) -> SandboxResult:
        code = """
        expr_str = data['expression']
        expr = sp.parse_expr(expr_str, local_dict=context)
        val = str(expr)
        try:
            val_eval = str(expr.evalf())
            if val_eval != val:
                val = f"{val} ({val_eval})"
        except Exception:
            pass
        latex_val = sp.latex(expr)
        
        # Try to simplify or expand to show some work steps
        steps = []
        steps.append(f"Parsed expression: {expr_str}")
        try:
            simplified = sp.simplify(expr)
            if simplified != expr:
                steps.append(f"Simplified to: {simplified}")
        except Exception:
            pass
            
        print(json.dumps({
            "value": str(expr),
            "latex": latex_val,
            "steps": steps,
            "verified": True
        }))
        """
        res = self._execute_in_isolated_process(code, {"expression": expression_str})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False)
        )

    def solve(self, equation_str: str, variable: str) -> SandboxResult:
        code = """
        eq_str = data['equation']
        var_str = data['variable']
        var = sp.Symbol(var_str)
        context[var_str] = var
        
        # Parse equation (if contains '=', split it and subtract rhs)
        if '=' in eq_str:
            lhs_str, rhs_str = eq_str.split('=', 1)
            lhs = sp.parse_expr(lhs_str, local_dict=context)
            rhs = sp.parse_expr(rhs_str, local_dict=context)
            eq = sp.Eq(lhs, rhs)
            expr_to_solve = lhs - rhs
        else:
            expr_to_solve = sp.parse_expr(eq_str, local_dict=context)
            eq = sp.Eq(expr_to_solve, 0)
            
        solutions = sp.solve(expr_to_solve, var)
        
        steps = [
            f"Solving equation: {eq}",
            f"Solving for variable: {var}"
        ]
        
        value = str(solutions)
        latex_val = sp.latex(solutions)
        
        print(json.dumps({
            "value": value,
            "latex": latex_val,
            "steps": steps,
            "verified": True
        }))
        """
        res = self._execute_in_isolated_process(code, {"equation": equation_str, "variable": variable})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False)
        )

    def integrate(self, expr: str, var: str) -> SandboxResult:
        code = """
        expr_str = data['expr']
        var_str = data['var']
        v = sp.Symbol(var_str)
        context[var_str] = v
        
        expression = sp.parse_expr(expr_str, local_dict=context)
        res = sp.integrate(expression, v)
        
        steps = [
            f"Integrating {expression} with respect to {v}"
        ]
        
        print(json.dumps({
            "value": str(res),
            "latex": sp.latex(res),
            "steps": steps,
            "verified": True
        }))
        """
        res = self._execute_in_isolated_process(code, {"expr": expr, "var": var})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False)
        )

    def differentiate(self, expr: str, var: str) -> SandboxResult:
        code = """
        expr_str = data['expr']
        var_str = data['var']
        v = sp.Symbol(var_str)
        context[var_str] = v
        
        expression = sp.parse_expr(expr_str, local_dict=context)
        res = sp.diff(expression, v)
        
        steps = [
            f"Differentiating {expression} with respect to {v}"
        ]
        
        print(json.dumps({
            "value": str(res),
            "latex": sp.latex(res),
            "steps": steps,
            "verified": True
        }))
        """
        res = self._execute_in_isolated_process(code, {"expr": expr, "var": var})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False)
        )

    def limit(self, expr: str, var: str, point: str) -> SandboxResult:
        code = """
        expr_str = data['expr']
        var_str = data['var']
        pt_str = data['point']
        
        v = sp.Symbol(var_str)
        context[var_str] = v
        
        expression = sp.parse_expr(expr_str, local_dict=context)
        pt = sp.parse_expr(pt_str, local_dict=context)
        
        res = sp.limit(expression, v, pt)
        
        steps = [
            f"Taking limit of {expression} as {v} approaches {pt}"
        ]
        
        print(json.dumps({
            "value": str(res),
            "latex": sp.latex(res),
            "steps": steps,
            "verified": True
        }))
        """
        res = self._execute_in_isolated_process(code, {"expr": expr, "var": var, "point": point})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False)
        )

    def series(self, expr: str, var: str, point: str, order: int) -> SandboxResult:
        code = """
        expr_str = data['expr']
        var_str = data['var']
        pt_str = data['point']
        n = data['order']
        
        v = sp.Symbol(var_str)
        context[var_str] = v
        
        expression = sp.parse_expr(expr_str, local_dict=context)
        pt = sp.parse_expr(pt_str, local_dict=context)
        
        res = sp.series(expression, v, pt, n)
        
        steps = [
            f"Expanding {expression} in a series around {v}={pt} up to order {n}"
        ]
        
        print(json.dumps({
            "value": str(res),
            "latex": sp.latex(res),
            "steps": steps,
            "verified": True
        }))
        """
        res = self._execute_in_isolated_process(code, {"expr": expr, "var": var, "point": point, "order": order})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False)
        )

    def matrix_ops(self, matrix_str: str, operation: str) -> SandboxResult:
        code = """
        mat_str = data['matrix']
        op = data['operation']
        
        # Expect matrix_str to be nested list e.g. [[1,2],[3,4]] or a SymPy Matrix string
        m = sp.Matrix(sp.parse_expr(mat_str, local_dict=context))
        
        steps = [f"Matrix: {m}"]
        
        if op == "determinant" or op == "det":
            res = m.det()
            steps.append("Calculating determinant")
        elif op == "inverse" or op == "inv":
            res = m.inv()
            steps.append("Calculating inverse matrix")
        elif op == "transpose" or op == "t":
            res = m.T
            steps.append("Calculating transpose matrix")
        elif op == "eigenvals" or op == "eigenvalues":
            res = m.eigenvals()
            steps.append("Calculating eigenvalues")
        elif op == "eigenvects" or op == "eigenvectors":
            res = m.eigenvects()
            steps.append("Calculating eigenvectors")
        elif op == "trace":
            res = m.trace()
            steps.append("Calculating trace")
        else:
            raise ValueError(f"Unknown matrix operation: {op}")
            
        print(json.dumps({
            "value": str(res),
            "latex": sp.latex(res),
            "steps": steps,
            "verified": True
        }))
        """
        res = self._execute_in_isolated_process(code, {"matrix": matrix_str, "operation": operation})
        if "error" in res:
            return SandboxResult(value="", latex="", verified=False, error=res["error"])
        return SandboxResult(
            value=res.get("value", ""),
            latex=res.get("latex", ""),
            steps=res.get("steps", []),
            verified=res.get("verified", False)
        )
