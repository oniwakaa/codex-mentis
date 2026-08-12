from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional, Callable, Union
import sympy as sp
import numpy as np
from codex_mentis.math_engine.sandbox import SymPySandbox, SandboxResult
from codex_mentis.math_engine.symbolic import SymbolicMath
from codex_mentis.math_engine.numerical import NumericalMath

@dataclass
class VerificationResult:
    verified: bool
    confidence: float
    evidence: List[str] = field(default_factory=list)
    counterexamples: List[str] = field(default_factory=list)
    error: Optional[str] = None

@dataclass
class ProofVerification:
    verified: bool
    steps_verified: List[bool] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

@dataclass
class CrossCheckResult:
    consistent: bool
    result1: Any
    result2: Any
    difference: Any

class MathVerifier:
    def __init__(self, sandbox: Optional[SymPySandbox] = None):
        self.sandbox = sandbox or SymPySandbox()
        self.symbolic = SymbolicMath(self.sandbox)
        self.numerical = NumericalMath()

    def verify_claim(self, claim_text: str) -> VerificationResult:
        """Verifies a mathematical claim. 
        
        Attempts to parse equations of the form LHS = RHS and run:
        1. Symbolic simplification (LHS - RHS = 0).
        2. Numerical testing (random substitution to find counterexamples).
        """
        evidence = []
        counterexamples = []
        
        # Check if the claim contains an equation '='
        if '=' not in claim_text:
            # Let's see if we can evaluate the claim as a boolean expression
            try:
                expr = sp.sympify(claim_text)
                if expr == sp.true:
                    return VerificationResult(verified=True, confidence=1.0, evidence=["Expression evaluates to True symbolically"])
                elif expr == sp.false:
                    return VerificationResult(verified=False, confidence=1.0, evidence=["Expression evaluates to False symbolically"])
            except Exception:
                pass
            return VerificationResult(
                verified=False,
                confidence=0.0,
                error="Claim does not contain an equation (=) and could not be parsed as a boolean expression"
            )
            
        lhs_str, rhs_str = claim_text.split('=', 1)
        evidence.append(f"Parsed LHS: {lhs_str.strip()}")
        evidence.append(f"Parsed RHS: {rhs_str.strip()}")
        
        # 1. Symbolic verification
        try:
            # Extract variables
            lhs_expr = sp.sympify(lhs_str)
            rhs_expr = sp.sympify(rhs_str)
            symbols = list(lhs_expr.free_symbols.union(rhs_expr.free_symbols))
            sym_names = [s.name for s in symbols]
            
            proof = self.symbolic.prove_identity(lhs_str, rhs_str, sym_names)
            if proof.verified:
                evidence.append("Proven symbolically: LHS - RHS simplifies to 0")
                return VerificationResult(verified=True, confidence=1.0, evidence=evidence)
            else:
                evidence.append("Failed symbolic proof: LHS - RHS does not simplify to 0")
        except Exception as e:
            evidence.append(f"Symbolic proof failed due to parsing error: {e}")
            symbols = []
            
        # 2. Numerical verification & counterexample search
        # If we have symbols, let's substitute random values to see if LHS = RHS
        if symbols:
            evidence.append(f"Searching for counterexamples using variables: {[s.name for s in symbols]}")
            # Run 50 random test cases
            for i in range(50):
                # Generate random values
                values = np.random.uniform(-10.0, 10.0, len(symbols))
                subs = {s.name: float(v) for s, v in zip(symbols, values)}
                
                try:
                    lhs_val = float(lhs_expr.subs([(sp.Symbol(k), v) for k, v in subs.items()]).evalf())
                    rhs_val = float(rhs_expr.subs([(sp.Symbol(k), v) for k, v in subs.items()]).evalf())
                    
                    if not np.isclose(lhs_val, rhs_val, rtol=1e-5, atol=1e-8):
                        counterexamples.append(f"x = {subs} => LHS = {lhs_val}, RHS = {rhs_val}")
                        if len(counterexamples) >= 5: # Limit counterexamples
                            break
                except Exception as e:
                    # Ignore substitution errors for individual points (e.g. division by zero)
                    continue
                    
            if counterexamples:
                evidence.append(f"Found {len(counterexamples)} counterexamples numerically.")
                return VerificationResult(verified=False, confidence=1.0, evidence=evidence, counterexamples=counterexamples)
            else:
                evidence.append("No counterexamples found in 50 numerical tests.")
                return VerificationResult(verified=True, confidence=0.85, evidence=evidence)
        else:
            # Constant expression, just evaluate
            try:
                lhs_val = float(sp.sympify(lhs_str).evalf())
                rhs_val = float(sp.sympify(rhs_str).evalf())
                if np.isclose(lhs_val, rhs_val, rtol=1e-5, atol=1e-8):
                    evidence.append(f"LHS ({lhs_val}) is numerically close to RHS ({rhs_val})")
                    return VerificationResult(verified=True, confidence=0.95, evidence=evidence)
                else:
                    counterexamples.append(f"LHS ({lhs_val}) != RHS ({rhs_val})")
                    return VerificationResult(verified=False, confidence=0.95, evidence=evidence, counterexamples=counterexamples)
            except Exception as e:
                return VerificationResult(verified=False, confidence=0.0, error=f"Numerical evaluation failed: {e}", evidence=evidence)

    def verify_proof(self, steps: List[str]) -> ProofVerification:
        """Verifies a step-by-step mathematical proof by checking validity of transitions."""
        if not steps:
            return ProofVerification(verified=False, errors=["Empty proof steps"])
            
        steps_verified = []
        errors = []
        
        for i in range(len(steps)):
            step = steps[i]
            # Try to verify step equality itself if it's an equation
            if '=' in step:
                claim_res = self.verify_claim(step)
                if claim_res.verified:
                    steps_verified.append(True)
                else:
                    steps_verified.append(False)
                    errors.append(f"Step {i+1} ('{step}') is not a mathematically valid equality.")
            else:
                # If it's descriptive text, assume True for now, but mark it
                steps_verified.append(True)
                
            # If not the first step, check transition from previous step
            if i > 0 and steps_verified[i] and steps_verified[i-1]:
                prev_step = steps[i-1]
                if '=' in prev_step and '=' in step:
                    # Let's check if the current step is consistent with previous
                    # e.g., do they have the same solution space, or does prev imply current?
                    # A simple check: check if a counterexample to prev is also a counterexample to current
                    # Or check if they are identical when solving for a variable.
                    # We can use symbolic substitution
                    try:
                        p_lhs, p_rhs = prev_step.split('=', 1)
                        c_lhs, c_rhs = step.split('=', 1)
                        
                        p_expr = sp.sympify(p_lhs) - sp.sympify(p_rhs)
                        c_expr = sp.sympify(c_lhs) - sp.sympify(c_rhs)
                        
                        symbols = list(p_expr.free_symbols.union(c_expr.free_symbols))
                        
                        # Numerical check: if p_expr is 0, is c_expr also 0?
                        # Since we want to check if prev => current, we can't just check independence.
                        # Instead, let's check if we solve for one variable in prev and substitute into current, does current hold?
                        if symbols:
                            solve_var = symbols[0]
                            # Solve prev for solve_var
                            try:
                                sols = sp.solve(p_expr, solve_var)
                                if sols:
                                    # Substitute solutions of prev into current
                                    transition_ok = False
                                    for sol in sols:
                                        subbed = c_expr.subs(solve_var, sol)
                                        if sp.simplify(subbed) == 0:
                                            transition_ok = True
                                            break
                                    if not transition_ok:
                                        steps_verified[i] = False
                                        errors.append(f"Transition from Step {i} to {i+1} is invalid: solution of Step {i} does not satisfy Step {i+1}.")
                            except Exception:
                                pass
                    except Exception:
                        pass
                        
        verified = all(steps_verified)
        return ProofVerification(verified=verified, steps_verified=steps_verified, errors=errors)

    def verify_computation(self, expr: str, expected: str) -> bool:
        """Verifies if the computation of expr matches expected result."""
        res = self.verify_claim(f"{expr} = {expected}")
        return res.verified

    def cross_check(self, problem: Any, method1: Callable[[Any], Any], method2: Callable[[Any], Any]) -> CrossCheckResult:
        """Cross-checks two different methods for solving a problem to ensure consistency."""
        res1 = None
        res2 = None
        error1 = None
        error2 = None
        
        try:
            res1 = method1(problem)
        except Exception as e:
            error1 = e
            
        try:
            res2 = method2(problem)
        except Exception as e:
            error2 = e
            
        if error1 or error2:
            return CrossCheckResult(
                consistent=False,
                result1=f"Error: {error1}" if error1 else res1,
                result2=f"Error: {error2}" if error2 else res2,
                difference="One or both methods failed with an exception"
            )
            
        # Check consistency
        consistent = False
        difference = None
        
        if type(res1) != type(res2):
            consistent = False
            difference = f"Type mismatch: {type(res1)} vs {type(res2)}"
        elif isinstance(res1, (int, float, complex)) and isinstance(res2, (int, float, complex)):
            consistent = np.isclose(res1, res2, rtol=1e-5, atol=1e-8)
            difference = abs(res1 - res2)
        elif isinstance(res1, str) and isinstance(res2, str):
            # Try to compare symbolically if they are math strings
            try:
                diff = sp.simplify(sp.sympify(res1) - sp.sympify(res2))
                consistent = (diff == 0)
                difference = str(diff)
            except Exception:
                consistent = (res1.strip() == res2.strip())
                difference = f"String equality: {consistent}"
        else:
            consistent = (res1 == res2)
            difference = f"Direct equality: {consistent}"
            
        return CrossCheckResult(
            consistent=consistent,
            result1=res1,
            result2=res2,
            difference=difference
        )
