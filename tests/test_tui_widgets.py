from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from pitagora.cli.rich_ui import build_equation_block, build_plot, build_table
from pitagora.teaching.ui import (
    build_comprehension_gauge,
    build_controls,
    build_subconcept_progress,
)


def render(renderable):
    console = Console(record=True, width=80)
    console.print(renderable)
    return console.export_text()


def test_equation_builder_returns_panel():
    result = build_equation_block(
        [{"equation": r"x^2", "annotation": "square"}],
        title="Math",
    )
    assert isinstance(result, Panel)
    assert "(1)" in render(result)


def test_table_builder_expands_and_stripes_rows():
    result = build_table(["A"], [["one"], ["two"]], title="Data")
    assert result.expand is True
    assert result.row_styles == ["none", "dim"]


def test_plot_builder_returns_titled_panel():
    result = build_plot([0, 1], [0, 1], "Line", "x", "y")
    assert isinstance(result, Panel)
    assert result.title == "Line"


def test_compact_teaching_builders_return_renderables():
    gauge = build_comprehension_gauge(0.75)
    progress = build_subconcept_progress(
        [{"name": "Definition", "mastery": 0.8, "visited": True}],
        0,
        compact=True,
    )
    controls = build_controls()
    assert isinstance(gauge, Text)
    assert isinstance(progress, Text)
    assert isinstance(controls, Text)
