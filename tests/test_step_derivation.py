"""Tests for Step-by-Step Derivation & Fallacy Verification Engine."""

from pitagora.math_engine.derivation import DerivationVerifier, DerivationReport


def test_valid_algebraic_derivation():
    verifier = DerivationVerifier()
    steps = [
        "(x + 1)**2",
        "(x + 1) * (x + 1)",
        "x**2 + 2*x + 1",
    ]
    justifications = ["Expand binomial", "Multiply polynomials"]
    report = verifier.verify_derivation(steps, justifications)

    assert isinstance(report, DerivationReport)
    assert report.is_valid_derivation is True
    assert report.total_steps == 2
    assert report.first_invalid_step is None


def test_invalid_algebraic_step_detected():
    verifier = DerivationVerifier()
    steps = [
        "(x + 1)**2",
        "x**2 + 1",  # Common freshman error (missing 2x)
        "x**2 + 1",
    ]
    report = verifier.verify_derivation(steps)

    assert report.is_valid_derivation is False
    assert report.first_invalid_step == 1
    assert "Difference" in report.steps[0].error_reason


def test_trigonometric_identity_derivation():
    verifier = DerivationVerifier()
    steps = [
        "sin(x)**2 + cos(x)**2",
        "1",
    ]
    report = verifier.verify_derivation(steps)
    assert report.is_valid_derivation is True
    assert report.steps[0].is_valid is True
    assert report.steps[0].detected_rule == "Trigonometric Identity"


def test_equation_step_transformation():
    verifier = DerivationVerifier()
    steps = [
        "2*x + 4 = 10",
        "2*x = 6",
        "x = 3",
    ]
    report = verifier.verify_derivation(steps)
    assert report.is_valid_derivation is True
