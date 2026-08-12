"""Tests for visualization improvements (TASK 5)."""
import io

from rich.console import Console

from pitagora.cli.rich_ui import (
    print_concept_map, print_math, print_equation_block, print_mastery_dashboard,
)


def _capture(func, *args, **kwargs) -> str:
    """Run a rich_ui print function against a capturing console and return its output."""
    import pitagora.cli.rich_ui as ui
    buf = io.StringIO()
    orig = ui.console
    cap = Console(file=buf, force_terminal=False, width=120, color_system=None)
    ui.console = cap
    try:
        func(*args, **kwargs)
        return buf.getvalue()
    finally:
        ui.console = orig


def test_print_math_return_str():
    # return_str path yields a string without printing.
    out = print_math(r"x^2 + 1", return_str=True)
    assert isinstance(out, str)
    assert "x" in out  # superscript substitution or sympy pretty


def test_print_math_prints_by_default():
    out = _capture(print_math, r"x^2")
    assert "Math Formula" in out


def test_print_concept_map_mastery_colors():
    relations = {"root": ["a", "b"], "a": [], "b": []}
    names = {"root": "Root", "a": "Alpha", "b": "Beta"}
    mastery = {"a": 0.9, "b": 0.3}
    out = _capture(
        print_concept_map, "root", relations, names, mastery_scores=mastery,
        current_concept="a",
    )
    # Current concept marker present
    assert "▸" in out
    # Both children appear
    assert "Alpha" in out
    assert "Beta" in out


def test_print_concept_map_dim_when_no_mastery():
    relations = {"root": ["a"]}
    names = {"root": "Root", "a": "Alpha"}
    out = _capture(print_concept_map, "root", relations, names)
    assert "Alpha" in out


def test_equation_block_renders_numbered():
    eqs = [
        {"equation": r"F = ma", "annotation": "Newton's second law"},
        {"equation": r"E = mc^2"},
    ]
    out = _capture(print_equation_block, eqs, title="Physics")
    assert "(1)" in out
    assert "(2)" in out
    assert "Newton" in out
    assert "Physics" in out


def test_mastery_dashboard_table():
    by_domain = {
        "algebra": {"concepts": 5, "mastered": 4, "avg_score": 0.85},
        "philosophy": {"concepts": 10, "mastered": 1, "avg_score": 0.2},
    }
    journeys = [{"topic": "limits", "status": "active", "interaction_count": 3}]
    out = _capture(print_mastery_dashboard, by_domain, journeys)
    assert "Mastery Dashboard" in out
    assert "algebra" in out
    assert "philosophy" in out
    assert "Active journeys" in out
    assert "limits" in out
