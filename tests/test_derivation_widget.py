"""Tests for DerivationView widget and derivation step navigation."""

from pitagora.tui.widgets.derivation_view import DerivationStep, DerivationView


def test_derivation_step_creation():
    step = DerivationStep(
        step_number=1,
        title="Define the Action Functional",
        equation_latex=r"S[q] = \int_{t_1}^{t_2} L(q, \dot{q}, t) dt",
        justification="Definition of classical action in configuration space",
        annotations=["L is the Lagrangian", "T - V"],
    )
    assert step.step_number == 1
    assert "Action" in step.title
    assert len(step.annotations) == 2


def test_derivation_view_navigation():
    steps = [
        DerivationStep(step_number=1, title="Step 1", equation_latex="a = b", justification="Premise"),
        DerivationStep(step_number=2, title="Step 2", equation_latex="b = c", justification="Premise"),
        DerivationStep(step_number=3, title="Step 3", equation_latex="a = c", justification="Transitivity"),
    ]
    view = DerivationView(title="Transitivity of Equality", steps=steps)
    assert view.current_step == 0

    assert view.next_step() is True
    assert view.current_step == 1

    assert view.next_step() is True
    assert view.current_step == 2

    # At boundary
    assert view.next_step() is False
    assert view.current_step == 2

    assert view.prev_step() is True
    assert view.current_step == 1
