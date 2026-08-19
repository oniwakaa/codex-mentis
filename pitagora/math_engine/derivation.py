"""Step-by-Step Derivation & Fallacy Verification Engine.

Validates multi-step mathematical & symbolic derivations, checks step-to-step
equivalence, identifies applied transformation rules, and pinpoints algebraic
or logical fallacies with surgical precision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import sympy as sp
from pitagora.math_engine.safe_parser import (
    safe_parse_expression,
    restricted_sympy_transform,
    SafeParseError,
)


@dataclass
class StepTransition:
    step_num: int
    from_expr: str
    to_expr: str
    justification: str = ""
    is_valid: bool = False
    detected_rule: str = ""
    latex_from: str = ""
    latex_to: str = ""
    error_reason: str | None = None


@dataclass
class DerivationReport:
    steps: list[StepTransition] = field(default_factory=list)
    is_valid_derivation: bool = False
    total_steps: int = 0
    first_invalid_step: int | None = None
    summary: str = ""


class DerivationVerifier:
    """Verifies sequential mathematical derivation steps."""

    def verify_derivation(
        self,
        steps: list[str],
        justifications: list[str] | None = None,
        variables: list[str] | None = None,
    ) -> DerivationReport:
        """Verifies an ordered sequence of mathematical expressions."""
        if not steps or len(steps) < 2:
            return DerivationReport(
                is_valid_derivation=True if len(steps) == 1 else False,
                total_steps=len(steps),
                summary="A derivation requires at least 2 consecutive steps to verify transitions.",
            )

        justifications = justifications or [""] * (len(steps) - 1)
        transitions: list[StepTransition] = []
        is_all_valid = True
        first_invalid = None

        for idx in range(len(steps) - 1):
            e_from = steps[idx].strip()
            e_to = steps[idx + 1].strip()
            just = justifications[idx] if idx < len(justifications) else ""

            transition = self.verify_single_step(
                step_num=idx + 1,
                from_expr=e_from,
                to_expr=e_to,
                justification=just,
                variables=variables,
            )
            transitions.append(transition)

            if not transition.is_valid and is_all_valid:
                is_all_valid = False
                first_invalid = idx + 1

        summary = (
            f"All {len(transitions)} derivation steps are mathematically sound."
            if is_all_valid
            else f"Derivation failed at Step {first_invalid}: {transitions[first_invalid - 1].error_reason}"
        )

        return DerivationReport(
            steps=transitions,
            is_valid_derivation=is_all_valid,
            total_steps=len(transitions),
            first_invalid_step=first_invalid,
            summary=summary,
        )

    def _parse_expr_safe(self, expr_str: str, variables: list[str] | None = None) -> Any:
        """Safely parses a mathematical string into a SymPy expression."""
        tree = safe_parse_expression(expr_str)
        local_dict = {v: sp.Symbol(v) for v in (variables or ["x", "y", "z", "t", "a", "b", "c", "theta"])}
        return restricted_sympy_transform(tree, local_dict=local_dict)

    def verify_single_step(
        self,
        step_num: int,
        from_expr: str,
        to_expr: str,
        justification: str = "",
        variables: list[str] | None = None,
    ) -> StepTransition:
        """Checks if from_expr mathematically transitions to to_expr."""
        # Check for equation equality transition (e.g. LHS = RHS)
        if "=" in from_expr and "=" in to_expr:
            return self._verify_equation_step(step_num, from_expr, to_expr, justification, variables)

        try:
            e1 = self._parse_expr_safe(from_expr, variables)
            e2 = self._parse_expr_safe(to_expr, variables)
        except Exception as e:
            return StepTransition(
                step_num=step_num,
                from_expr=from_expr,
                to_expr=to_expr,
                justification=justification,
                is_valid=False,
                error_reason=f"Syntax or safety check failed: {e}",
            )

        try:
            diff = sp.simplify(e1 - e2)
            is_equiv = (diff == 0)
            
            has_trig = any(fn in from_expr or fn in to_expr for fn in ["sin", "cos", "tan", "sinh", "cosh", "tanh"])
            has_rad = any(fn in from_expr or fn in to_expr for fn in ["sqrt", "**(1/2)", "**(0.5)"])
            
            if has_trig:
                rule = "Trigonometric Identity"
            elif has_rad:
                rule = "Radical Simplification"
            else:
                rule = "Algebraic Equivalence"

            if not is_equiv:
                trig_diff = sp.trigsimp(diff)
                if trig_diff == 0:
                    is_equiv = True
                    rule = "Trigonometric Identity"
                else:
                    rad_diff = sp.radsimp(diff)
                    if rad_diff == 0:
                        is_equiv = True
                        rule = "Radical Simplification"

            latex_1 = sp.latex(e1)
            latex_2 = sp.latex(e2)

            error_msg = None if is_equiv else f"Expressions are not algebraically equivalent (Difference: {diff})"

            return StepTransition(
                step_num=step_num,
                from_expr=from_expr,
                to_expr=to_expr,
                justification=justification or rule,
                is_valid=is_equiv,
                detected_rule=rule if is_equiv else "",
                latex_from=latex_1,
                latex_to=latex_2,
                error_reason=error_msg,
            )
        except Exception as exc:
            return StepTransition(
                step_num=step_num,
                from_expr=from_expr,
                to_expr=to_expr,
                justification=justification,
                is_valid=False,
                error_reason=f"SymPy evaluation error: {exc}",
            )

    def _verify_equation_step(
        self,
        step_num: int,
        eq1_str: str,
        eq2_str: str,
        justification: str,
        variables: list[str] | None = None,
    ) -> StepTransition:
        """Verifies transitions between full equations (LHS = RHS)."""
        l1_str, r1_str = eq1_str.split("=", 1)
        l2_str, r2_str = eq2_str.split("=", 1)

        try:
            l1 = self._parse_expr_safe(l1_str.strip(), variables)
            r1 = self._parse_expr_safe(r1_str.strip(), variables)
            l2 = self._parse_expr_safe(l2_str.strip(), variables)
            r2 = self._parse_expr_safe(r2_str.strip(), variables)
        except Exception as e:
            return StepTransition(
                step_num=step_num,
                from_expr=eq1_str,
                to_expr=eq2_str,
                justification=justification,
                is_valid=False,
                error_reason=f"Equation syntax error: {e}",
            )

        try:
            eq1_diff = sp.simplify(l1 - r1)
            eq2_diff = sp.simplify(l2 - r2)

            equiv = (sp.simplify(eq1_diff - eq2_diff) == 0) or (sp.simplify(eq1_diff + eq2_diff) == 0)

            if not equiv and eq2_diff != 0:
                ratio = sp.simplify(eq1_diff / eq2_diff)
                if ratio.is_number and ratio != 0:
                    equiv = True

            latex_1 = f"{sp.latex(l1)} = {sp.latex(r1)}"
            latex_2 = f"{sp.latex(l2)} = {sp.latex(r2)}"

            return StepTransition(
                step_num=step_num,
                from_expr=eq1_str,
                to_expr=eq2_str,
                justification=justification or "Equation Transformation",
                is_valid=equiv,
                detected_rule="Equation Transformation" if equiv else "",
                latex_from=latex_1,
                latex_to=latex_2,
                error_reason=None if equiv else f"Equation transformation is invalid (Diff 1: {eq1_diff}, Diff 2: {eq2_diff})",
            )
        except Exception as exc:
            return StepTransition(
                step_num=step_num,
                from_expr=eq1_str,
                to_expr=eq2_str,
                justification=justification,
                is_valid=False,
                error_reason=f"Equation verification failed: {exc}",
            )
