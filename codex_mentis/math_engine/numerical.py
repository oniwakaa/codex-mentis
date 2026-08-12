from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional, Callable, Union
import numpy as np
import scipy as sc
import scipy.optimize as opt
import scipy.integrate as integrate
import sympy as sp

@dataclass
class OptimalPoint:
    x: Union[float, List[float]]
    fun: float
    success: bool
    message: str

class NumericalMath:
    def __init__(self):
        pass

    def evaluate_float(self, expr: str, precision: int = 15) -> float:
        """Evaluates a mathematical expression to a floating point number with specified precision."""
        # Use SymPy to parse and evaluate to float
        parsed = sp.sympify(expr)
        val = parsed.evalf(n=precision)
        return float(val)

    def plot_data(self, func_str: str, x_range: Tuple[float, float, int]) -> Tuple[List[float], List[float]]:
        """Generates (x_values, y_values) for plotting a function over a range."""
        start, end, steps = x_range
        x_vals = np.linspace(start, end, steps)
        
        # Parse expression and lambdify it
        x_sym = sp.Symbol('x')
        expr = sp.sympify(func_str)
        f_lambdified = sp.lambdify(x_sym, expr, modules=['numpy', 'sympy'])
        
        # Evaluate y values
        y_vals = []
        for x in x_vals:
            try:
                y = float(f_lambdified(x))
            except Exception:
                y = float('nan')
            y_vals.append(y)
            
        return x_vals.tolist(), y_vals

    def solve_numeric(self, equation_str: str, initial_guess: float) -> float:
        """Solves an equation numerically using fsolve starting from initial_guess."""
        if '=' in equation_str:
            lhs_str, rhs_str = equation_str.split('=', 1)
            expr = sp.sympify(lhs_str) - sp.sympify(rhs_str)
        else:
            expr = sp.sympify(equation_str)
            
        x_sym = sp.Symbol('x')
        f_lambdified = sp.lambdify(x_sym, expr, modules=['numpy', 'sympy'])
        
        def objective(x):
            return f_lambdified(x)
            
        res = opt.fsolve(objective, initial_guess)
        return float(res[0])

    def optimize(self, objective_str: str, constraints: Optional[List[Dict[str, Any]]] = None) -> OptimalPoint:
        """Minimizes an objective function.
        
        objective_str can be a function of 'x' (for 1D) or a function containing 'x0', 'x1', etc.
        For example: 'x**2 + 4*x' or 'x0**2 + x1**2'
        """
        # Determine variable names
        expr = sp.sympify(objective_str)
        symbols = sorted(list(expr.free_symbols), key=lambda s: s.name)
        
        if len(symbols) == 0:
            return OptimalPoint(x=0.0, fun=0.0, success=False, message="No variables in objective function")
            
        # Lambdify the function
        f_lambdified = sp.lambdify(symbols, expr, modules=['numpy', 'sympy'])
        
        if len(symbols) == 1:
            # 1D optimization
            def f_1d(x):
                val = f_lambdified(x[0])
                if hasattr(val, "item"):
                    return float(val.item())
                return float(val)
            res = opt.minimize(f_1d, x0=np.array([0.0]))
            return OptimalPoint(
                x=float(res.x[0]),
                fun=float(res.fun),
                success=bool(res.success),
                message=str(res.message)
            )
        else:
            # Multi-dimensional optimization
            def f_md(x):
                val = f_lambdified(*x)
                if hasattr(val, "item"):
                    return float(val.item())
                return float(val)
                
            x0 = [0.0] * len(symbols)
            
            # Parse constraints if any
            scipy_constraints = []
            if constraints:
                for c in constraints:
                    # c has 'type' ('eq' or 'ineq') and 'fun' string
                    c_expr = sp.sympify(c['fun'])
                    c_lambdified = sp.lambdify(symbols, c_expr, modules=['numpy', 'sympy'])
                    def c_func(x, cl=c_lambdified):
                        val = cl(*x)
                        if hasattr(val, "item"):
                            return float(val.item())
                        return float(val)
                    scipy_constraints.append({
                        'type': c['type'],
                        'fun': c_func
                    })
                    
            res = opt.minimize(f_md, x0=x0, constraints=scipy_constraints)
            return OptimalPoint(
                x=res.x.tolist(),
                fun=float(res.fun),
                success=bool(res.success),
                message=str(res.message)
            )

    def integrate_numeric(self, func_str: str, bounds: Tuple[float, float]) -> float:
        """Numerically integrates func_str from bounds[0] to bounds[1] using quad."""
        x_sym = sp.Symbol('x')
        expr = sp.sympify(func_str)
        f_lambdified = sp.lambdify(x_sym, expr, modules=['numpy', 'sympy'])
        
        def integrand(x):
            return float(f_lambdified(x))
            
        val, _ = integrate.quad(integrand, bounds[0], bounds[1])
        return float(val)

    def eigenvalues_numeric(self, matrix_str: str) -> List[complex]:
        """Calculates eigenvalues of a matrix numerically."""
        # matrix_str can be a list of lists format or numpy format
        # e.g., "[[1, 2], [3, 4]]"
        matrix_data = eval(matrix_str)
        np_matrix = np.array(matrix_data, dtype=float)
        eigenvals = np.linalg.eigvals(np_matrix)
        # Convert np complex to python complex list
        return [complex(val) for val in eigenvals]
